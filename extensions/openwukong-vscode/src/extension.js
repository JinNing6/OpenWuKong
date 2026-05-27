"use strict";

const http = require("http");
const vscode = require("vscode");

let server = null;
let serverAddress = "";

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand("openwukong.startBridge", async () => {
      await startBridge(context);
    })
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("openwukong.stopBridge", async () => {
      await stopBridge();
    })
  );

  const config = vscode.workspace.getConfiguration("openwukong");
  if (config.get("bridge.autoStart", false)) {
    startBridge(context).catch((error) => {
      vscode.window.showWarningMessage(`OpenWukong bridge failed to start: ${error.message}`);
    });
  }
}

async function startBridge(context) {
  if (server) {
    vscode.window.showInformationMessage(`OpenWukong bridge already running at ${serverAddress}`);
    return serverAddress;
  }

  const config = vscode.workspace.getConfiguration("openwukong");
  const host = config.get("bridge.host", "127.0.0.1");
  const port = config.get("bridge.port", 8787);

  server = http.createServer((request, response) => {
    handleRequest(request, response).catch((error) => {
      writeJson(response, 500, {
        ok: false,
        error: error.message || String(error)
      });
    });
  });

  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, host, resolve);
  });

  serverAddress = `http://${host}:${port}`;
  context.subscriptions.push({ dispose: () => stopBridge() });
  vscode.window.showInformationMessage(`OpenWukong bridge started at ${serverAddress}`);
  return serverAddress;
}

async function stopBridge() {
  if (!server) {
    return;
  }
  const closing = server;
  server = null;
  serverAddress = "";
  await new Promise((resolve) => closing.close(resolve));
}

async function handleRequest(request, response) {
  if (request.method !== "POST") {
    writeJson(response, 405, { ok: false, error: "method_not_allowed" });
    return;
  }

  if (request.url === "/v1/ide/read") {
    const payload = await readJson(request);
    writeJson(response, 200, {
      ok: true,
      conversation: buildConversationSummary(payload),
      metadata: buildSessionMetadata()
    });
    return;
  }

  if (request.url === "/v1/ide/send") {
    const payload = await readJson(request);
    const result = await handleSend(payload);
    writeJson(response, result.ok ? 200 : 409, result);
    return;
  }

  if (request.url === "/v1/ide/state") {
    const payload = await readJson(request);
    writeJson(response, 200, {
      ok: true,
      conversation: buildConversationSummary(payload),
      metadata: buildSessionMetadata(),
      diagnostics: buildDiagnostics()
    });
    return;
  }

  if (request.url === "/v1/ide/command") {
    const payload = await readJson(request);
    const result = await handleCommand(payload);
    writeJson(response, result.ok ? 200 : 403, result);
    return;
  }

  if (request.url === "/v1/ide/capabilities") {
    const commands = await vscode.commands.getCommands(true);
    writeJson(response, 200, {
      ok: true,
      metadata: buildSessionMetadata(),
      commands,
      chat_adapters: buildChatAdapters(commands)
    });
    return;
  }

  if (request.url === "/v1/ide/chat") {
    const payload = await readJson(request);
    const result = await handleChat(payload);
    writeJson(response, result.ok ? 200 : 409, result);
    return;
  }

  writeJson(response, 404, { ok: false, error: "not_found" });
}

async function handleSend(payload) {
  const config = vscode.workspace.getConfiguration("openwukong");
  const commandId = config.get("bridge.sendCommand", "");
  const message = typeof payload.message === "string" ? payload.message : "";

  if (!message.trim()) {
    return {
      ok: false,
      error: "empty_message",
      metadata: buildSessionMetadata()
    };
  }

  if (!commandId) {
    return {
      ok: false,
      error: "send_command_not_configured",
      conversation: buildConversationSummary(payload),
      metadata: {
        ...buildSessionMetadata(),
        command_id: ""
      }
    };
  }

  await vscode.commands.executeCommand(commandId, {
    message,
    target: payload.target || {},
    metadata: buildSessionMetadata()
  });

  return {
    ok: true,
    action_key: `ide-extension:${Date.now()}`,
    conversation: buildConversationSummary(payload),
    metadata: {
      ...buildSessionMetadata(),
      command_id: commandId
    }
  };
}

async function handleCommand(payload) {
  const commandId = typeof payload.command_id === "string" ? payload.command_id.trim() : "";
  const config = vscode.workspace.getConfiguration("openwukong");
  const allowedCommands = config.get("bridge.allowedCommands", []);
  const allowed = Array.isArray(allowedCommands) ? allowedCommands : [];
  const args = Array.isArray(payload.arguments) ? payload.arguments : [];

  if (!commandId) {
    return {
      ok: false,
      error: "missing_command_id",
      metadata: buildSessionMetadata()
    };
  }

  if (!allowed.includes(commandId)) {
    return {
      ok: false,
      error: "command_not_allowlisted",
      metadata: {
        ...buildSessionMetadata(),
        command_id: commandId
      }
    };
  }

  const result = await vscode.commands.executeCommand(commandId, ...args);
  return {
    ok: true,
    action_key: `ide-command:${Date.now()}`,
    metadata: {
      ...buildSessionMetadata(),
      command_id: commandId
    },
    result: summarizeCommandResult(result)
  };
}

async function handleChat(payload) {
  const adapterId = typeof payload.adapter_id === "string" ? payload.adapter_id.trim() : "";
  const message = typeof payload.message === "string" ? payload.message : "";
  const metadata = buildSessionMetadata();

  if (!adapterId) {
    return {
      ok: false,
      error: "missing_chat_adapter",
      metadata
    };
  }

  if (!message.trim()) {
    return {
      ok: false,
      error: "empty_message",
      metadata: {
        ...metadata,
        adapter_id: adapterId
      }
    };
  }

  const commands = await vscode.commands.getCommands(true);
  const adapters = buildChatAdapters(commands);
  const adapter = adapters.find((item) => item.adapter_id === adapterId);
  if (!adapter) {
    return {
      ok: false,
      error: "chat_adapter_not_configured",
      metadata: {
        ...metadata,
        adapter_id: adapterId
      },
      chat_adapters: adapters
    };
  }

  if (!adapter.available) {
    return {
      ok: false,
      error: "chat_adapter_unavailable",
      metadata: {
        ...metadata,
        adapter_id: adapterId,
        command_id: adapter.command_id
      },
      chat_adapters: adapters
    };
  }

  const result = await vscode.commands.executeCommand(adapter.command_id, {
    message,
    target: payload.target || {},
    metadata: {
      ...metadata,
      adapter_id: adapterId,
      command_id: adapter.command_id
    }
  });

  return {
    ok: true,
    action_key: `ide-chat:${Date.now()}`,
    conversation: buildConversationSummary({
      ...payload,
      action: "chat_send"
    }),
    metadata: {
      ...metadata,
      adapter_id: adapterId,
      command_id: adapter.command_id
    },
    result: summarizeCommandResult(result)
  };
}

function buildChatAdapters(commands) {
  const commandSet = new Set(Array.isArray(commands) ? commands : []);
  return getConfiguredChatAdapters().map((adapter) => {
    const availableCandidates = adapter.command_candidates.filter((commandId) => commandSet.has(commandId));
    const selectedCommandId = commandSet.has(adapter.command_id)
      ? adapter.command_id
      : (availableCandidates[0] || adapter.command_id);
    return {
      adapter_id: adapter.adapter_id,
      label: adapter.label,
      command_id: selectedCommandId,
      command_candidates: adapter.command_candidates,
      available: Boolean(selectedCommandId && commandSet.has(selectedCommandId)),
      available_candidates: availableCandidates
    };
  });
}

function getConfiguredChatAdapters() {
  const config = vscode.workspace.getConfiguration("openwukong");
  const chatAdapters = config.get("bridge.chatAdapters", {});
  if (!chatAdapters || typeof chatAdapters !== "object" || Array.isArray(chatAdapters)) {
    return [];
  }

  return Object.entries(chatAdapters).map(([adapterId, value]) => {
    const raw = value && typeof value === "object" && !Array.isArray(value)
      ? value
      : { commandId: typeof value === "string" ? value : "" };
    const commandId = typeof raw.commandId === "string" ? raw.commandId.trim() : "";
    const configuredCandidates = Array.isArray(raw.commandCandidates) ? raw.commandCandidates : [];
    const commandCandidates = [commandId, ...configuredCandidates]
      .filter((item) => typeof item === "string")
      .map((item) => item.trim())
      .filter(Boolean);
    return {
      adapter_id: adapterId,
      label: typeof raw.label === "string" && raw.label.trim() ? raw.label.trim() : adapterId,
      command_id: commandId,
      command_candidates: Array.from(new Set(commandCandidates))
    };
  });
}

function buildConversationSummary(payload) {
  const active = vscode.window.activeTextEditor;
  const lines = [
    `ide=${vscode.env.appName}`,
    `workspaceFolders=${(vscode.workspace.workspaceFolders || []).length}`
  ];
  if (active) {
    lines.push(`activeFile=${active.document.uri.fsPath}`);
    lines.push(`language=${active.document.languageId}`);
  }
  if (payload && payload.action) {
    lines.push(`action=${payload.action}`);
  }
  return lines.join("\n");
}

function buildSessionMetadata() {
  const active = vscode.window.activeTextEditor;
  const workspaceFolders = (vscode.workspace.workspaceFolders || []).map((folder) => ({
    name: folder.name,
    uri: folder.uri.toString(),
    fsPath: folder.uri.fsPath
  }));
  return {
    ide_name: vscode.env.appName,
    workspaceFolders,
    activeTextEditor: active
      ? {
          uri: active.document.uri.toString(),
          fsPath: active.document.uri.fsPath,
          languageId: active.document.languageId,
          isDirty: active.document.isDirty,
          selection: {
            start: active.selection.start.line,
            end: active.selection.end.line
          }
        }
      : null,
    visibleTextEditors: vscode.window.visibleTextEditors.length
  };
}

function buildDiagnostics() {
  const diagnostics = [];
  for (const [uri, items] of vscode.languages.getDiagnostics()) {
    for (const item of items) {
      diagnostics.push({
        uri: uri.toString(),
        fsPath: uri.fsPath,
        severity: item.severity,
        source: item.source || "",
        code: item.code ? String(item.code) : "",
        message: item.message,
        line: item.range.start.line,
        character: item.range.start.character
      });
    }
  }
  return diagnostics;
}

function summarizeCommandResult(result) {
  if (result === undefined) {
    return null;
  }
  if (result === null || typeof result === "string" || typeof result === "number" || typeof result === "boolean") {
    return result;
  }
  try {
    return JSON.parse(JSON.stringify(result));
  } catch (_error) {
    return String(result);
  }
}

function readJson(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("error", reject);
    request.on("end", () => {
      const body = Buffer.concat(chunks).toString("utf8");
      if (!body.trim()) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(body));
      } catch (error) {
        reject(new Error(`invalid_json: ${error.message}`));
      }
    });
  });
}

function writeJson(response, statusCode, data) {
  const body = Buffer.from(JSON.stringify(data), "utf8");
  response.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": body.length
  });
  response.end(body);
}

function deactivate() {
  return stopBridge();
}

module.exports = {
  activate,
  deactivate
};
