"use strict";

const crypto = require("crypto");
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");
const vscode = require("vscode");

const CURSOR_CREATE_NEW_COMPOSER_COMMAND = "composer.createNew";
const CURSOR_SELECTED_COMPOSER_IDS_COMMAND = "composer.getOrderedSelectedComposerIds";
const CURSOR_COMPOSER_HANDLE_COMMAND = "composer.getComposerHandleById";
const CURSOR_GLASS_NEW_AGENT_WITH_QUERY_COMMANDS = ["glass.newAgentWithQuery", "newAgentWithQuery"];
const ISOLATED_CURSOR_READ_PROFILE = "isolated_cursor_read_probe";
const ISOLATED_CURSOR_DRAFT_PROFILE = "isolated_cursor_draft_probe";
const LIVE_CURSOR_ATTACH_DRAFT_PROFILE = "live_cursor_attach_draft_probe";
const LIVE_CURSOR_ATTACH_DRAFT_WRITE_PROFILE = "live_cursor_attach_draft_write_probe";
const LIVE_CURSOR_GLASS_AGENT_QUERY_PROFILE = "live_cursor_glass_agent_query_probe";
const DANGEROUS_CURSOR_COMMANDS = new Set([CURSOR_COMPOSER_HANDLE_COMMAND]);
const IDE_BRIDGE_REGISTRY_SCHEMA_VERSION = "openwukong-ide-bridge-registry-v1";
const OPENAI_CODEX_EXTENSION_ID = "openai.chatgpt";
const CODEX_COMMAND_ROLES = [
  {
    command_id: "chatgpt.addToThread",
    role: "context_only",
    prompt_send: false,
    reason: "adds active editor or selection context to the current Codex thread"
  },
  {
    command_id: "chatgpt.addFileToThread",
    role: "context_only",
    prompt_send: false,
    reason: "adds a file URI as context to the current Codex thread"
  },
  {
    command_id: "chatgpt.newChat",
    role: "surface_open",
    prompt_send: false,
    reason: "opens or starts a new Codex sidebar thread without a prompt argument"
  },
  {
    command_id: "chatgpt.newCodexPanel",
    role: "surface_open",
    prompt_send: false,
    reason: "creates a Codex agent panel without a prompt argument"
  },
  {
    command_id: "chatgpt.openSidebar",
    role: "surface_open",
    prompt_send: false,
    reason: "opens the Codex sidebar"
  },
  {
    command_id: "chatgpt.openCommandMenu",
    role: "surface_open",
    prompt_send: false,
    reason: "opens the Codex command menu"
  },
  {
    command_id: "chatgpt.showLspMcpCliArgs",
    role: "diagnostic",
    prompt_send: false,
    reason: "copies or shows LSP MCP CLI arguments"
  }
];
const OWNED_SCRATCH_DIR = ".openwukong";
const OWNED_SCRATCH_FILE = "openwukong-owned-scratch.txt";

let server = null;
let serverAddress = "";
let serverStatePath = "";

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand("openwukong.startBridge", async () => {
      await startBridge(context, { notify: true });
    })
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("openwukong.stopBridge", async () => {
      await stopBridge();
    })
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("openwukong.writeScratch", async (payload) => {
      return writeOwnedScratch(payload);
    })
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("openwukong.readScratch", async () => {
      return readOwnedScratch();
    })
  );

  const config = vscode.workspace.getConfiguration("openwukong");
  if (config.get("bridge.autoStart", false)) {
    const started = maybeAutoStartBridge(context, config);
    if (!started) {
      const workspaceListener = vscode.workspace.onDidChangeWorkspaceFolders(() => {
        if (!server) {
          maybeAutoStartBridge(context, vscode.workspace.getConfiguration("openwukong"));
        }
      });
      context.subscriptions.push(workspaceListener);
    }
  }
}

function maybeAutoStartBridge(context, config) {
  if (config.get("bridge.autoStartRequiresWorkspace", true) && !hasWorkspaceFolder()) {
    console.warn("OpenWukong bridge auto-start skipped: workspace folder required");
    return false;
  }
  startBridge(context, { notify: false }).catch((error) => {
    if (!config.get("bridge.silentAutoStartFailures", true)) {
      vscode.window.showWarningMessage(
        `OpenWukong bridge auto-start skipped: ${error.message}`
      );
    }
    console.warn(`OpenWukong bridge auto-start skipped: ${error.message}`);
  });
  return true;
}

function hasWorkspaceFolder() {
  return Array.isArray(vscode.workspace.workspaceFolders) && vscode.workspace.workspaceFolders.length > 0;
}

async function startBridge(context, options = {}) {
  const notify = options.notify === true;
  if (server) {
    if (notify) {
      vscode.window.showInformationMessage(`OpenWukong bridge already running at ${serverAddress}`);
    }
    return serverAddress;
  }

  const config = vscode.workspace.getConfiguration("openwukong");
  const host = config.get("bridge.host", "127.0.0.1");
  const preferredPort = config.get("bridge.port", 0);
  const autoPortOnConflict = config.get("bridge.autoPortOnConflict", true);
  const dynamicPortOnConflict = config.get("bridge.dynamicPortOnConflict", true);
  const fallbackAttempts = config.get("bridge.portFallbackAttempts", 20);
  const result = await listenBridgeServer(host, preferredPort, {
    autoPortOnConflict,
    dynamicPortOnConflict,
    fallbackAttempts
  });

  server = result.server;
  serverAddress = `http://${host}:${result.port}`;
  serverStatePath = await safeWriteBridgeRegistryState(context, host, result);
  context.subscriptions.push({ dispose: () => stopBridge() });
  if (notify) {
    vscode.window.showInformationMessage(`OpenWukong bridge started at ${serverAddress}`);
  }
  return serverAddress;
}

function createBridgeServer() {
  return http.createServer((request, response) => {
    handleRequest(request, response).catch((error) => {
      writeJson(response, 500, {
        ok: false,
        error: error.message || String(error)
      });
    });
  });
}

async function listenBridgeServer(host, preferredPort, options) {
  const normalizedPreferredPort = normalizePort(preferredPort);
  if (normalizedPreferredPort === 0) {
    const candidate = createBridgeServer();
    const bound = await listenOnPort(candidate, host, 0);
    return {
      server: candidate,
      port: bound.port,
      preferredPort: 0,
      dynamicPort: true
    };
  }
  const fallbackAttempts = Math.max(1, Number(options.fallbackAttempts) || 1);
  const maxAttempts = options.autoPortOnConflict ? fallbackAttempts : 1;
  let lastError = null;
  for (let offset = 0; offset < maxAttempts; offset += 1) {
    const port = normalizedPreferredPort + offset;
    if (port > 65535) {
      break;
    }
    const candidate = createBridgeServer();
    try {
      const bound = await listenOnPort(candidate, host, port);
      return {
        server: candidate,
        port: bound.port,
        preferredPort: normalizedPreferredPort,
        dynamicPort: false
      };
    } catch (error) {
      lastError = error;
      try {
        candidate.close();
      } catch (_) {
        // Ignore close failures for servers that never reached listening.
      }
      if (!error || error.code !== "EADDRINUSE") {
        throw error;
      }
    }
  }
  if (options.autoPortOnConflict && options.dynamicPortOnConflict) {
    const candidate = createBridgeServer();
    const bound = await listenOnPort(candidate, host, 0);
    return {
      server: candidate,
      port: bound.port,
      preferredPort: normalizedPreferredPort,
      dynamicPort: true
    };
  }
  throw lastError || new Error("bridge_port_unavailable");
}

function listenOnPort(candidate, host, port) {
  return new Promise((resolve, reject) => {
    const onError = (error) => {
      candidate.removeListener("listening", onListening);
      reject(error);
    };
    const onListening = () => {
      candidate.removeListener("error", onError);
      resolve({ port: listeningPort(candidate, port) });
    };
    candidate.once("error", onError);
    candidate.once("listening", onListening);
    candidate.listen(port, host);
  });
}

function listeningPort(candidate, fallbackPort) {
  const address = candidate.address();
  if (address && typeof address === "object" && typeof address.port === "number") {
    return address.port;
  }
  return fallbackPort;
}

function normalizePort(value) {
  const port = Number(value);
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    throw new Error(`invalid_bridge_port:${value}`);
  }
  return port;
}

async function writeBridgeRegistryState(context, host, listenResult) {
  const registryRoot = bridgeRegistryRoot();
  const statePath = path.join(registryRoot, `${bridgeInstanceKey(context)}.json`);
  const workspaceFolders = (vscode.workspace.workspaceFolders || []).map((folder) => ({
    name: folder.name,
    uri: folder.uri.toString(),
    fsPath: folder.uri.fsPath
  }));
  const bridge = {
    type: "ide_bridge",
    enabled: true,
    app_name: vscode.env.appName,
    bridge_url: serverAddress,
    url: serverAddress,
    host,
    port: listenResult.port,
    preferred_port: listenResult.preferredPort,
    dynamic_port: Boolean(listenResult.dynamicPort),
    workspace_folders: workspaceFolders,
    process_id: typeof process !== "undefined" ? process.pid : 0,
    updated_at: new Date().toISOString()
  };
  const payload = {
    schema_version: IDE_BRIDGE_REGISTRY_SCHEMA_VERSION,
    ide_bridges: [bridge]
  };
  await fs.promises.mkdir(registryRoot, { recursive: true });
  await fs.promises.writeFile(statePath, JSON.stringify(payload, null, 2), "utf8");
  return statePath;
}

async function safeWriteBridgeRegistryState(context, host, listenResult) {
  try {
    return await writeBridgeRegistryState(context, host, listenResult);
  } catch (error) {
    console.warn(`OpenWukong bridge registry write skipped: ${error.message || String(error)}`);
    return "";
  }
}

function bridgeRegistryRoot() {
  const base = process.env.LOCALAPPDATA || os.tmpdir();
  return path.join(base, "OpenWukong", "ide-bridges");
}

function bridgeInstanceKey(context) {
  const workspaceFolders = (vscode.workspace.workspaceFolders || [])
    .map((folder) => folder.uri.toString())
    .join("|");
  const seed = [
    vscode.env.appName,
    typeof process !== "undefined" ? String(process.pid || "") : "",
    context && context.globalStorageUri ? context.globalStorageUri.toString() : "",
    workspaceFolders
  ].join("|");
  return crypto.createHash("sha256").update(seed).digest("hex").slice(0, 24);
}

async function stopBridge() {
  if (!server) {
    return;
  }
  const closing = server;
  const statePath = serverStatePath;
  server = null;
  serverAddress = "";
  serverStatePath = "";
  await new Promise((resolve) => closing.close(resolve));
  if (statePath) {
    await fs.promises.unlink(statePath).catch(() => {});
  }
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

  if (request.url === "/v1/ide/codex/capabilities") {
    const payload = await readJson(request);
    const result = await handleCodexCapabilities(payload);
    writeJson(response, 200, result);
    return;
  }

  if (request.url === "/v1/ide/cursor/composer-state") {
    const payload = await readJson(request);
    const result = await handleCursorComposerState(payload);
    writeJson(response, result.ok ? 200 : 409, result);
    return;
  }

  if (request.url === "/v1/ide/cursor/draft-hook") {
    const payload = await readJson(request);
    const result = await handleCursorDraftHook(payload);
    writeJson(response, result.ok ? 200 : 409, result);
    return;
  }

  if (request.url === "/v1/ide/cursor/glass-agent-query") {
    const payload = await readJson(request);
    const result = await handleCursorGlassAgentQuery(payload);
    writeJson(response, result.ok ? 200 : 409, result);
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

async function handleCodexCapabilities(_payload) {
  const commands = await vscode.commands.getCommands(true);
  const commandSet = new Set(commands);
  const extension = vscode.extensions.getExtension(OPENAI_CODEX_EXTENSION_ID);
  const packageJson = extension && extension.packageJSON ? extension.packageJSON : {};
  const extensionExports = extension && extension.isActive ? extension.exports : null;
  const contributedCommands = codexContributedCommands(packageJson);
  const contributedCommandSet = new Set(contributedCommands.map((item) => item.command_id));
  const commandRoles = CODEX_COMMAND_ROLES.map((item) => ({
    ...item,
    available: commandSet.has(item.command_id),
    contributed: contributedCommandSet.has(item.command_id)
  }));
  const promptSendCommands = commandRoles.filter((item) => item.available && item.prompt_send);
  const installed = Boolean(extension);
  const requiresWebviewBridge = installed && promptSendCommands.length === 0;
  return {
    ok: installed,
    action_key: `codex-capabilities:${Date.now()}`,
    decision: installed
      ? (requiresWebviewBridge ? "codex_webview_bridge_required" : "codex_prompt_command_available")
      : "codex_extension_missing",
    metadata: buildSessionMetadata(),
    extension: {
      id: OPENAI_CODEX_EXTENSION_ID,
      installed,
      active: Boolean(extension && extension.isActive),
      extension_path: safeString(extension && extension.extensionPath),
      package_name: safeString(packageJson.name),
      publisher: safeString(packageJson.publisher),
      version: safeString(packageJson.version),
      display_name: safeString(packageJson.displayName),
      exports_type: describeValueType(extensionExports),
      export_keys: safeOwnPropertyNames(extensionExports).slice(0, 80)
    },
    contributed_commands: contributedCommands,
    command_roles: commandRoles,
    prompt_send_ready: promptSendCommands.length > 0,
    prompt_send_commands: promptSendCommands.map((item) => item.command_id),
    requires_webview_bridge: requiresWebviewBridge,
    webview_route_hints: [
      "composer_prefill",
      "shared-object-set",
      "open-vscode-command"
    ],
    control_attempts: 0,
    window_input_attempts: 0,
    keyboard_input_attempts: 0,
    clipboard_write_attempts: 0,
    error: installed ? "" : "openai_codex_extension_missing"
  };
}

function codexContributedCommands(packageJson) {
  const commands = packageJson
    && packageJson.contributes
    && Array.isArray(packageJson.contributes.commands)
    ? packageJson.contributes.commands
    : [];
  return commands
    .filter((item) => item && typeof item.command === "string" && item.command.startsWith("chatgpt."))
    .map((item) => ({
      command_id: safeString(item.command),
      title: safeString(item.title),
      category: safeString(item.category)
    }));
}

async function handleCommand(payload) {
  const commandId = typeof payload.command_id === "string" ? payload.command_id.trim() : "";
  const config = vscode.workspace.getConfiguration("openwukong");
  const allowedCommands = config.get("bridge.allowedCommands", []);
  const allowed = Array.isArray(allowedCommands) ? allowedCommands : [];
  const args = Array.isArray(payload.arguments) ? payload.arguments : [];
  const safety = commandSafetyDecision(commandId, payload);

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

  if (!safety.allowed) {
    return {
      ok: false,
      error: safety.error,
      metadata: {
        ...buildSessionMetadata(),
        command_id: commandId,
        safety_profile: safety.safety_profile,
        required_safety_profiles: safety.required_safety_profiles
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

function commandSafetyDecision(commandId, payload) {
  const safetyProfile = typeof payload.safety_profile === "string" ? payload.safety_profile : "";
  if (!DANGEROUS_CURSOR_COMMANDS.has(commandId)) {
    return {
      allowed: true,
      safety_profile: safetyProfile,
      required_safety_profiles: []
    };
  }
  const requiredProfiles = [ISOLATED_CURSOR_READ_PROFILE, ISOLATED_CURSOR_DRAFT_PROFILE];
  if (requiredProfiles.includes(safetyProfile)) {
    return {
      allowed: true,
      safety_profile: safetyProfile,
      required_safety_profiles: requiredProfiles
    };
  }
  return {
    allowed: false,
    error: "cursor_command_requires_isolated_profile",
    safety_profile: safetyProfile,
    required_safety_profiles: requiredProfiles
  };
}

async function writeOwnedScratch(payload) {
  const metadata = buildSessionMetadata();
  const message = ownedScratchMessage(payload);
  if (!message.trim()) {
    throw new Error("owned_scratch_message_missing");
  }
  const scratch = ownedScratchTarget();
  await vscode.workspace.fs.createDirectory(scratch.dirUri);
  await vscode.workspace.fs.writeFile(scratch.fileUri, Buffer.from(message, "utf8"));
  const readback = Buffer.from(await vscode.workspace.fs.readFile(scratch.fileUri)).toString("utf8");
  const ok = readback === message;
  return {
    ok,
    action_key: `owned-ide-scratch:${Date.now()}`,
    command_id: "openwukong.writeScratch",
    workspace_uri: scratch.workspaceUri.toString(),
    workspace_path: scratch.workspacePath,
    scratch_uri: scratch.fileUri.toString(),
    scratch_path: scratch.scratchPath,
    readback_text: readback,
    readback_verified: ok,
    metadata,
    window_input_attempts: 0,
    keyboard_input_attempts: 0,
    clipboard_write_attempts: 0,
    foreground_focus_stable: true,
    error: ok ? "" : "owned_scratch_readback_mismatch"
  };
}

async function readOwnedScratch() {
  const scratch = ownedScratchTarget();
  let readback = "";
  let exists = true;
  try {
    readback = Buffer.from(await vscode.workspace.fs.readFile(scratch.fileUri)).toString("utf8");
  } catch (_error) {
    exists = false;
  }
  return {
    ok: exists,
    command_id: "openwukong.readScratch",
    workspace_uri: scratch.workspaceUri.toString(),
    workspace_path: scratch.workspacePath,
    scratch_uri: scratch.fileUri.toString(),
    scratch_path: scratch.scratchPath,
    readback_text: readback,
    readback_verified: exists,
    window_input_attempts: 0,
    keyboard_input_attempts: 0,
    clipboard_write_attempts: 0,
    foreground_focus_stable: true,
    error: exists ? "" : "owned_scratch_missing"
  };
}

function ownedScratchTarget() {
  const folders = vscode.workspace.workspaceFolders || [];
  if (!folders.length) {
    throw new Error("owned_scratch_workspace_missing");
  }
  const workspace = folders[0];
  const dirUri = vscode.Uri.joinPath(workspace.uri, OWNED_SCRATCH_DIR);
  const fileUri = vscode.Uri.joinPath(dirUri, OWNED_SCRATCH_FILE);
  const workspacePath = workspace.uri.fsPath || "";
  return {
    workspaceUri: workspace.uri,
    workspacePath,
    dirUri,
    fileUri,
    scratchPath: workspacePath
      ? path.join(workspacePath, OWNED_SCRATCH_DIR, OWNED_SCRATCH_FILE)
      : fileUri.toString()
  };
}

function ownedScratchMessage(payload) {
  if (typeof payload === "string") {
    return payload;
  }
  if (payload && typeof payload === "object") {
    for (const key of ["message", "text", "marker"]) {
      if (typeof payload[key] === "string") {
        return payload[key];
      }
    }
  }
  return "";
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

  const commandArguments = buildChatCommandArguments(
    adapter.command_id,
    message,
    payload,
    metadata,
    adapterId
  );
  const config = vscode.workspace.getConfiguration("openwukong");
  const commandAwaitTimeoutMs = config.get("bridge.chatCommandAwaitTimeoutMs", 2500);
  const dispatch = await executeCommandWithBoundedAwait(
    adapter.command_id,
    commandArguments,
    commandAwaitTimeoutMs
  );

  if (dispatch.status === "rejected") {
    return {
      ok: false,
      error: dispatch.error || "chat_command_rejected",
      metadata: {
        ...metadata,
        adapter_id: adapterId,
        command_id: adapter.command_id
      },
      chat_adapters: adapters
    };
  }

  return {
    ok: true,
    action_key: `ide-chat:${Date.now()}`,
    dispatch_status: dispatch.status,
    conversation: buildConversationSummary({
      ...payload,
      action: "chat_send"
    }),
    metadata: {
      ...metadata,
      adapter_id: adapterId,
      command_id: adapter.command_id
    },
    result: dispatch.status === "resolved"
      ? summarizeCommandResult(dispatch.result)
      : {
          pending: true,
          timeout_ms: dispatch.timeout_ms,
          command_id: adapter.command_id
        }
  };
}

async function executeCommandWithBoundedAwait(commandId, args, timeoutMs) {
  return executePromiseWithBoundedAwait(
    commandId,
    () => vscode.commands.executeCommand(commandId, ...args),
    timeoutMs
  );
}

async function executePromiseWithBoundedAwait(label, promiseFactory, timeoutMs) {
  const waitMs = normalizeCommandAwaitTimeout(timeoutMs);
  let timeoutHandle = null;
  const commandOutcome = Promise.resolve()
    .then(() => promiseFactory())
    .then(
      (result) => ({ status: "resolved", result }),
      (error) => ({
        status: "rejected",
        error: error && error.message ? error.message : String(error)
      })
  );
  commandOutcome.then((outcome) => {
    if (outcome.status === "rejected") {
      console.warn(`OpenWukong command rejected (${label}): ${outcome.error}`);
    }
  });
  const timeoutOutcome = new Promise((resolve) => {
    timeoutHandle = setTimeout(
      () => resolve({ status: "pending", timeout_ms: waitMs }),
      waitMs
    );
    if (timeoutHandle && typeof timeoutHandle.unref === "function") {
      timeoutHandle.unref();
    }
  });
  const outcome = await Promise.race([commandOutcome, timeoutOutcome]);
  if (timeoutHandle) {
    clearTimeout(timeoutHandle);
  }
  return outcome;
}

function normalizeCommandAwaitTimeout(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return 2500;
  }
  return Math.max(100, Math.min(60000, Math.floor(parsed)));
}

async function handleCursorComposerState(payload) {
  const commands = await vscode.commands.getCommands(true);
  const commandSet = new Set(commands);
  const metadata = buildSessionMetadata();
  const config = vscode.workspace.getConfiguration("openwukong");
  const commandAwaitTimeoutMs = config.get("bridge.cursorReadCommandAwaitTimeoutMs", 2500);

  if (!commandSet.has(CURSOR_SELECTED_COMPOSER_IDS_COMMAND)) {
    return {
      ok: false,
      error: "cursor_selected_composer_command_unavailable",
      metadata
    };
  }
  const includeHandles = payload.include_handles === true || payload.includeHandles === true;
  const safetyProfile = typeof payload.safety_profile === "string" ? payload.safety_profile : "";
  const allowHandleRead = includeHandles && safetyProfile === ISOLATED_CURSOR_READ_PROFILE;
  if (allowHandleRead && !commandSet.has(CURSOR_COMPOSER_HANDLE_COMMAND)) {
    return {
      ok: false,
      error: "cursor_composer_handle_command_unavailable",
      metadata
    };
  }

  const requestedIds = Array.isArray(payload.composer_ids)
    ? payload.composer_ids.filter((item) => typeof item === "string" && item.trim()).map((item) => item.trim())
    : [];
  const pendingCommands = [];
  const commandErrors = [];
  const selectedDispatch = await executeCommandWithBoundedAwait(
    CURSOR_SELECTED_COMPOSER_IDS_COMMAND,
    [],
    commandAwaitTimeoutMs
  );
  let selectedIds = [];
  if (selectedDispatch.status === "resolved") {
    selectedIds = uniqueStrings(selectedDispatch.result);
  } else if (selectedDispatch.status === "pending") {
    pendingCommands.push({
      command_id: CURSOR_SELECTED_COMPOSER_IDS_COMMAND,
      timeout_ms: selectedDispatch.timeout_ms
    });
  } else {
    commandErrors.push({
      command_id: CURSOR_SELECTED_COMPOSER_IDS_COMMAND,
      error: selectedDispatch.error || "cursor_selected_composer_command_rejected"
    });
  }
  const ids = uniqueStrings(requestedIds.length ? requestedIds : selectedIds);
  const composers = [];
  if (allowHandleRead) {
    for (const composerId of ids.slice(0, 8)) {
      const handleDispatch = await executeCommandWithBoundedAwait(
        CURSOR_COMPOSER_HANDLE_COMMAND,
        [composerId],
        commandAwaitTimeoutMs
      );
      if (handleDispatch.status === "resolved") {
        composers.push(summarizeComposerHandle(handleDispatch.result, composerId));
      } else if (handleDispatch.status === "pending") {
        pendingCommands.push({
          command_id: CURSOR_COMPOSER_HANDLE_COMMAND,
          composer_id: composerId,
          timeout_ms: handleDispatch.timeout_ms
        });
      } else {
        commandErrors.push({
          command_id: CURSOR_COMPOSER_HANDLE_COMMAND,
          composer_id: composerId,
          error: handleDispatch.error || "cursor_composer_handle_command_rejected"
        });
      }
    }
  }
  const stateStatus = pendingCommands.length > 0
    ? "pending"
    : (composers.length > 0 ? "ready" : (ids.length > 0 ? "selected_only" : "missing"));

  return {
    ok: commandErrors.length === 0,
    action_key: `cursor-composer-state:${Date.now()}`,
    state_status: stateStatus,
    metadata,
    selected_composer_ids: uniqueStrings(selectedIds),
    requested_composer_ids: requestedIds,
    composer_ids: ids,
    composers,
    include_handles: includeHandles,
    handle_read_allowed: allowHandleRead,
    handle_read_policy: allowHandleRead ? ISOLATED_CURSOR_READ_PROFILE : "isolated_cursor_read_probe_required",
    pending_commands: pendingCommands,
    command_errors: commandErrors,
    error: commandErrors.length > 0 ? "cursor_composer_state_command_rejected" : ""
  };
}

async function handleCursorDraftHook(payload) {
  const metadata = buildSessionMetadata();
  const message = typeof payload.message === "string" ? payload.message : "";
  const allowWrite = payload.allow_write === true;
  const safetyProfile = typeof payload.safety_profile === "string" ? payload.safety_profile : "";
  const isolatedDraftProbe = safetyProfile === ISOLATED_CURSOR_DRAFT_PROFILE;
  const liveAttachDraftProbe = safetyProfile === LIVE_CURSOR_ATTACH_DRAFT_PROFILE;
  const liveAttachDraftWriteProbe = safetyProfile === LIVE_CURSOR_ATTACH_DRAFT_WRITE_PROFILE;
  const dryRun = !allowWrite;

  if (!message.trim()) {
    return {
      ok: false,
      decision: "cursor_draft_hook_message_missing",
      error: "empty_message",
      metadata
    };
  }
  if (allowWrite && liveAttachDraftProbe) {
    return {
      ok: false,
      decision: "cursor_draft_hook_live_write_blocked",
      error: "cursor_draft_hook_live_write_requires_live_write_profile",
      metadata,
      dry_run: false,
      can_write_draft: false,
      handle_read_allowed: false,
      handle_read_policy: "live_cursor_attach_draft_write_probe_required"
    };
  }
  if (allowWrite && !isolatedDraftProbe && !liveAttachDraftWriteProbe) {
    return {
      ok: false,
      decision: "cursor_draft_hook_write_blocked",
      error: "cursor_draft_hook_write_requires_explicit_profile",
      metadata,
      dry_run: dryRun,
      can_write_draft: false,
      handle_read_allowed: false,
      handle_read_policy: "isolated_or_live_draft_write_profile_required"
    };
  }
  if (!allowWrite && !isolatedDraftProbe && !liveAttachDraftProbe && !liveAttachDraftWriteProbe) {
    return {
      ok: false,
      decision: "cursor_draft_hook_read_blocked",
      error: "cursor_draft_hook_read_requires_isolated_or_live_profile",
      metadata,
      dry_run: dryRun,
      can_write_draft: false,
      handle_read_allowed: false,
      handle_read_policy: "isolated_cursor_draft_probe_required"
    };
  }

  const config = vscode.workspace.getConfiguration("openwukong");
  const commandAwaitTimeoutMs = config.get(
    "bridge.cursorDraftHookCommandAwaitTimeoutMs",
    config.get("bridge.cursorReadCommandAwaitTimeoutMs", 2500)
  );
  const commandsDispatch = await executePromiseWithBoundedAwait(
    "vscode.commands.getCommands",
    () => vscode.commands.getCommands(true),
    commandAwaitTimeoutMs
  );
  if (commandsDispatch.status === "pending") {
    return {
      ok: false,
      decision: "cursor_draft_hook_command_pending",
      error: "cursor_draft_hook_commands_pending",
      metadata,
      dry_run: dryRun,
      can_write_draft: false,
      command_await_timeout_ms: normalizeCommandAwaitTimeout(commandAwaitTimeoutMs),
      pending_commands: [
        {
          command_id: "vscode.commands.getCommands",
          timeout_ms: commandsDispatch.timeout_ms
        }
      ]
    };
  }
  if (commandsDispatch.status === "rejected") {
    return {
      ok: false,
      decision: "cursor_draft_hook_command_rejected",
      error: commandsDispatch.error || "cursor_draft_hook_commands_rejected",
      metadata,
      dry_run: dryRun,
      can_write_draft: false,
      command_errors: [
        {
          command_id: "vscode.commands.getCommands",
          error: commandsDispatch.error || "cursor_draft_hook_commands_rejected"
        }
      ]
    };
  }

  const commands = Array.isArray(commandsDispatch.result) ? commandsDispatch.result : [];
  const commandSet = new Set(commands);
  if ((liveAttachDraftProbe || liveAttachDraftWriteProbe) && dryRun) {
    const createNewAvailable = commandSet.has(CURSOR_CREATE_NEW_COMPOSER_COMMAND);
    return {
      ok: createNewAvailable,
      decision: createNewAvailable
        ? (liveAttachDraftWriteProbe
            ? "cursor_draft_hook_live_attach_write_ready"
            : "cursor_draft_hook_live_attach_ready")
        : "cursor_draft_hook_live_attach_create_new_unavailable",
      error: createNewAvailable ? "" : "cursor_create_new_composer_command_unavailable",
      action_key: `cursor-draft-hook-live-attach-plan:${Date.now()}`,
      metadata,
      dry_run: true,
      can_write_draft: createNewAvailable,
      mutation_strategy: createNewAvailable ? "command_create_new_composer" : "none",
      command_await_timeout_ms: normalizeCommandAwaitTimeout(commandAwaitTimeoutMs),
      handle_read_allowed: false,
      handle_read_policy: "isolated_cursor_draft_probe_required",
      live_attach_profile: liveAttachDraftWriteProbe
        ? LIVE_CURSOR_ATTACH_DRAFT_WRITE_PROFILE
        : LIVE_CURSOR_ATTACH_DRAFT_PROFILE
    };
  }
  if (liveAttachDraftWriteProbe) {
    if (!commandSet.has(CURSOR_CREATE_NEW_COMPOSER_COMMAND)) {
      return {
        ok: false,
        decision: "cursor_draft_hook_live_attach_create_new_unavailable",
        error: "cursor_create_new_composer_command_unavailable",
        metadata,
        dry_run: false,
        can_write_draft: false,
        mutation_strategy: "none",
        handle_read_allowed: false,
        handle_read_policy: "isolated_cursor_draft_probe_required"
      };
    }
    const mutation = await applyCursorLiveAttachDraftMutation(message, commandAwaitTimeoutMs);
    if (!mutation.ok) {
      return {
        ok: false,
        decision: "cursor_draft_hook_live_attach_mutation_failed",
        error: mutation.error || "cursor_live_attach_draft_mutation_failed",
        metadata,
        dry_run: false,
        can_write_draft: false,
        mutation_strategy: mutation.strategy,
        handle_read_allowed: false,
        handle_read_policy: "isolated_cursor_draft_probe_required",
        pending_command: mutation.pending_command,
        command_error: mutation.command_error
      };
    }
    return {
      ok: true,
      decision: "cursor_draft_hook_live_attach_written",
      action_key: `cursor-draft-hook-live-attach:${Date.now()}`,
      metadata,
      dry_run: false,
      can_write_draft: true,
      mutation_strategy: mutation.strategy,
      composer_id: mutation.composer_id || "",
      created_result: mutation.created_result,
      handle_read_allowed: false,
      handle_read_policy: "isolated_cursor_draft_probe_required",
      readback_policy: "cursor_local_storage_user_draft_marker_required"
    };
  }
  if (!commandSet.has(CURSOR_SELECTED_COMPOSER_IDS_COMMAND)) {
    return {
      ok: false,
      decision: "cursor_draft_hook_selected_ids_unavailable",
      error: "cursor_selected_composer_command_unavailable",
      metadata
    };
  }
  if (!commandSet.has(CURSOR_COMPOSER_HANDLE_COMMAND)) {
    return {
      ok: false,
      decision: "cursor_draft_hook_handle_unavailable",
      error: "cursor_composer_handle_command_unavailable",
      metadata
    };
  }

  const requestedIds = Array.isArray(payload.composer_ids)
    ? payload.composer_ids.filter((item) => typeof item === "string" && item.trim()).map((item) => item.trim())
    : [];
  const selectedDispatch = await executeCommandWithBoundedAwait(
    CURSOR_SELECTED_COMPOSER_IDS_COMMAND,
    [],
    commandAwaitTimeoutMs
  );
  if (selectedDispatch.status === "pending") {
    return {
      ok: false,
      decision: "cursor_draft_hook_command_pending",
      error: "cursor_selected_composer_command_pending",
      metadata,
      dry_run: dryRun,
      can_write_draft: false,
      pending_commands: [
        {
          command_id: CURSOR_SELECTED_COMPOSER_IDS_COMMAND,
          timeout_ms: selectedDispatch.timeout_ms
        }
      ]
    };
  }
  if (selectedDispatch.status === "rejected") {
    return {
      ok: false,
      decision: "cursor_draft_hook_command_rejected",
      error: selectedDispatch.error || "cursor_selected_composer_command_rejected",
      metadata,
      dry_run: dryRun,
      can_write_draft: false,
      command_errors: [
        {
          command_id: CURSOR_SELECTED_COMPOSER_IDS_COMMAND,
          error: selectedDispatch.error || "cursor_selected_composer_command_rejected"
        }
      ]
    };
  }
  const selectedIds = selectedDispatch.result;
  const ids = uniqueStrings(requestedIds.length ? requestedIds : selectedIds);
  const composerId = ids[0] || "";
  if (!composerId) {
    return {
      ok: false,
      decision: "cursor_draft_hook_composer_missing",
      error: "cursor_composer_id_missing",
      metadata,
      selected_composer_ids: uniqueStrings(selectedIds),
      requested_composer_ids: requestedIds
    };
  }

  const handleDispatch = await executeCommandWithBoundedAwait(
    CURSOR_COMPOSER_HANDLE_COMMAND,
    [composerId],
    commandAwaitTimeoutMs
  );
  if (handleDispatch.status === "pending") {
    return {
      ok: false,
      decision: "cursor_draft_hook_command_pending",
      error: "cursor_composer_handle_command_pending",
      metadata,
      dry_run: dryRun,
      can_write_draft: false,
      composer_id: composerId,
      selected_composer_ids: uniqueStrings(selectedIds),
      requested_composer_ids: requestedIds,
      pending_commands: [
        {
          command_id: CURSOR_COMPOSER_HANDLE_COMMAND,
          composer_id: composerId,
          timeout_ms: handleDispatch.timeout_ms
        }
      ]
    };
  }
  if (handleDispatch.status === "rejected") {
    return {
      ok: false,
      decision: "cursor_draft_hook_command_rejected",
      error: handleDispatch.error || "cursor_composer_handle_command_rejected",
      metadata,
      dry_run: dryRun,
      can_write_draft: false,
      composer_id: composerId,
      selected_composer_ids: uniqueStrings(selectedIds),
      requested_composer_ids: requestedIds,
      command_errors: [
        {
          command_id: CURSOR_COMPOSER_HANDLE_COMMAND,
          composer_id: composerId,
          error: handleDispatch.error || "cursor_composer_handle_command_rejected"
        }
      ]
    };
  }
  const handle = handleDispatch.result;
  const handleDiagnostics = collectCursorHandleDiagnostics(handle, composerId);
  const mutationPlan = planCursorDraftMutation(handle, composerId, commandSet);
  const canWriteDraft = mutationPlan.can_write;
  const before = summarizeComposerHandle(handle, composerId);
  if (dryRun) {
    return {
      ok: canWriteDraft,
      decision: canWriteDraft ? "cursor_draft_hook_ready" : "cursor_draft_hook_set_data_unavailable",
      action_key: `cursor-draft-hook-plan:${Date.now()}`,
      metadata,
      dry_run: true,
      can_write_draft: canWriteDraft,
      mutation_strategy: mutationPlan.strategy,
      composer_id: composerId,
      selected_composer_ids: uniqueStrings(selectedIds),
      requested_composer_ids: requestedIds,
      before,
      handle_diagnostics: handleDiagnostics,
      write_method_candidates: handleDiagnostics.write_method_candidates
    };
  }

  if (!canWriteDraft) {
    return {
      ok: false,
      decision: "cursor_draft_hook_set_data_unavailable",
      error: "cursor_composer_handle_set_data_unavailable",
      metadata,
      dry_run: false,
      can_write_draft: false,
      mutation_strategy: mutationPlan.strategy,
      composer_id: composerId,
      before,
      handle_diagnostics: handleDiagnostics,
      write_method_candidates: handleDiagnostics.write_method_candidates
    };
  }

  const mutation = await applyCursorDraftMutation(
    handle,
    composerId,
    message,
    commandSet,
    commandAwaitTimeoutMs
  );
  if (!mutation.ok) {
    return {
      ok: false,
      decision: "cursor_draft_hook_mutation_failed",
      error: mutation.error || "cursor_draft_mutation_failed",
      metadata,
      dry_run: false,
      can_write_draft: false,
      mutation_strategy: mutation.strategy,
      composer_id: composerId,
      before,
      handle_diagnostics: handleDiagnostics,
      write_method_candidates: handleDiagnostics.write_method_candidates
    };
  }
  const writtenComposerId = mutation.composer_id || composerId;
  const after = mutation.after || summarizeComposerHandle(handle, writtenComposerId);
  return {
    ok: true,
    decision: "cursor_draft_hook_written",
    action_key: `cursor-draft-hook:${Date.now()}`,
    metadata,
    dry_run: false,
    can_write_draft: true,
    mutation_strategy: mutation.strategy,
    composer_id: writtenComposerId,
    selected_composer_ids: uniqueStrings(selectedIds),
    requested_composer_ids: requestedIds,
    before,
    after
  };
}

async function handleCursorGlassAgentQuery(payload) {
  const metadata = buildSessionMetadata();
  const message = typeof payload.message === "string" ? payload.message : "";
  const allowWrite = payload.allow_write === true;
  const safetyProfile = typeof payload.safety_profile === "string" ? payload.safety_profile : "";
  const liveAgentQueryProbe = safetyProfile === LIVE_CURSOR_GLASS_AGENT_QUERY_PROFILE;
  const dryRun = !allowWrite;

  if (!message.trim()) {
    return {
      ok: false,
      decision: "cursor_glass_agent_query_message_missing",
      error: "empty_message",
      metadata
    };
  }
  if (allowWrite && !liveAgentQueryProbe) {
    return {
      ok: false,
      decision: "cursor_glass_agent_query_blocked",
      error: "cursor_glass_agent_query_requires_live_profile",
      metadata,
      dry_run: false,
      command_id: "",
      required_safety_profile: LIVE_CURSOR_GLASS_AGENT_QUERY_PROFILE,
      window_input_attempts: 0,
      keyboard_input_attempts: 0,
      clipboard_write_attempts: 0
    };
  }

  const config = vscode.workspace.getConfiguration("openwukong");
  const commandAwaitTimeoutMs = config.get(
    "bridge.cursorDraftHookCommandAwaitTimeoutMs",
    config.get("bridge.chatCommandAwaitTimeoutMs", 2500)
  );
  const commandsDispatch = await executePromiseWithBoundedAwait(
    "vscode.commands.getCommands",
    () => vscode.commands.getCommands(true),
    commandAwaitTimeoutMs
  );
  if (commandsDispatch.status === "pending") {
    return {
      ok: false,
      decision: "cursor_glass_agent_query_command_pending",
      error: "cursor_glass_agent_query_commands_pending",
      metadata,
      dry_run: dryRun,
      command_id: "",
      command_await_timeout_ms: normalizeCommandAwaitTimeout(commandAwaitTimeoutMs),
      pending_commands: [
        {
          command_id: "vscode.commands.getCommands",
          timeout_ms: commandsDispatch.timeout_ms
        }
      ],
      window_input_attempts: 0,
      keyboard_input_attempts: 0,
      clipboard_write_attempts: 0
    };
  }
  if (commandsDispatch.status === "rejected") {
    return {
      ok: false,
      decision: "cursor_glass_agent_query_command_rejected",
      error: commandsDispatch.error || "cursor_glass_agent_query_commands_rejected",
      metadata,
      dry_run: dryRun,
      command_id: "",
      command_errors: [
        {
          command_id: "vscode.commands.getCommands",
          error: commandsDispatch.error || "cursor_glass_agent_query_commands_rejected"
        }
      ],
      window_input_attempts: 0,
      keyboard_input_attempts: 0,
      clipboard_write_attempts: 0
    };
  }

  const commands = Array.isArray(commandsDispatch.result) ? commandsDispatch.result : [];
  const commandSet = new Set(commands);
  const commandId = selectCursorGlassAgentQueryCommand(commandSet);
  if (!commandId) {
    return {
      ok: false,
      decision: "cursor_glass_agent_query_unavailable",
      error: "cursor_glass_new_agent_with_query_command_unavailable",
      metadata,
      dry_run: dryRun,
      command_id: "",
      command_candidates: CURSOR_GLASS_NEW_AGENT_WITH_QUERY_COMMANDS,
      window_input_attempts: 0,
      keyboard_input_attempts: 0,
      clipboard_write_attempts: 0
    };
  }

  if (dryRun) {
    return {
      ok: true,
      decision: "cursor_glass_agent_query_ready",
      action_key: `cursor-glass-agent-query-plan:${Date.now()}`,
      metadata,
      dry_run: true,
      command_id: commandId,
      command_candidates: CURSOR_GLASS_NEW_AGENT_WITH_QUERY_COMMANDS,
      command_await_timeout_ms: normalizeCommandAwaitTimeout(commandAwaitTimeoutMs),
      safety_profile: safetyProfile,
      required_safety_profile: LIVE_CURSOR_GLASS_AGENT_QUERY_PROFILE,
      readback_policy: "cursor_local_storage_assistant_marker_required",
      window_input_attempts: 0,
      keyboard_input_attempts: 0,
      clipboard_write_attempts: 0
    };
  }

  const dispatch = await executeCommandWithBoundedAwait(
    commandId,
    [message],
    commandAwaitTimeoutMs
  );
  if (dispatch.status === "rejected") {
    return {
      ok: false,
      decision: "cursor_glass_agent_query_rejected",
      error: dispatch.error || "cursor_glass_agent_query_command_rejected",
      metadata,
      dry_run: false,
      command_id: commandId,
      dispatch_status: "rejected",
      command_error: {
        command_id: commandId,
        error: dispatch.error || "cursor_glass_agent_query_command_rejected"
      },
      window_input_attempts: 0,
      keyboard_input_attempts: 0,
      clipboard_write_attempts: 0
    };
  }

  return {
    ok: true,
    decision: "cursor_glass_agent_query_dispatched",
    action_key: `cursor-glass-agent-query:${Date.now()}`,
    metadata,
    dry_run: false,
    command_id: commandId,
    dispatch_status: dispatch.status,
    command_await_timeout_ms: normalizeCommandAwaitTimeout(commandAwaitTimeoutMs),
    result: dispatch.status === "resolved"
      ? summarizeCommandResult(dispatch.result)
      : {
          pending: true,
          timeout_ms: dispatch.timeout_ms,
          command_id: commandId
        },
    readback_policy: "cursor_local_storage_assistant_marker_required",
    window_input_attempts: 0,
    keyboard_input_attempts: 0,
    clipboard_write_attempts: 0
  };
}

function selectCursorGlassAgentQueryCommand(commandSet) {
  for (const commandId of CURSOR_GLASS_NEW_AGENT_WITH_QUERY_COMMANDS) {
    if (commandSet && commandSet.has(commandId)) {
      return commandId;
    }
  }
  return "";
}

function summarizeComposerHandle(handle, fallbackComposerId) {
  const state = findComposerState(handle, fallbackComposerId);
  const conversationMap = state && state.conversationMap && typeof state.conversationMap === "object"
    ? state.conversationMap
    : {};
  return {
    composer_id: safeString((state && state.composerId) || (handle && handle.composerId) || fallbackComposerId),
    has_handle: Boolean(handle),
    has_state: Boolean(state),
    text: safeString(state && state.text),
    rich_text: safeString(state && state.richText),
    status: safeString(state && state.status),
    unified_mode: safeString(state && state.unifiedMode),
    force_mode: safeString(state && state.forceMode),
    is_agentic: Boolean(state && state.isAgentic),
    has_pending_plan: Boolean(state && state.hasPendingPlan),
    has_blocking_pending_actions: Boolean(state && state.hasBlockingPendingActions),
    conversation_bubble_count: Object.keys(conversationMap).length,
    queue_item_count: Array.isArray(state && state.queueItems) ? state.queueItems.length : 0,
    root_prompt_count: Array.isArray(state && state.conversationState && state.conversationState.rootPromptMessagesJson)
      ? state.conversationState.rootPromptMessagesJson.length
      : 0,
    turn_count: Array.isArray(state && state.conversationState && state.conversationState.turns)
      ? state.conversationState.turns.length
      : 0
  };
}

function planCursorDraftMutation(handle, composerId, commandSet) {
  if (commandSet && commandSet.has(CURSOR_CREATE_NEW_COMPOSER_COMMAND)) {
    return {
      can_write: true,
      strategy: "command_create_new_composer"
    };
  }
  if (handle && typeof handle.setData === "function") {
    return {
      can_write: true,
      strategy: "handle_set_data"
    };
  }
  const state = findComposerState(handle, composerId);
  if (state && typeof state === "object" && ("text" in state || "richText" in state)) {
    return {
      can_write: false,
      strategy: "state_direct_patch_transient_unverified"
    };
  }
  return {
    can_write: false,
    strategy: "none"
  };
}

async function applyCursorDraftMutation(handle, composerId, message, commandSet, commandAwaitTimeoutMs) {
  if (commandSet && commandSet.has(CURSOR_CREATE_NEW_COMPOSER_COMMAND)) {
    const beforeComposerIds = collectComposerIdsFromHandle(handle);
    const createdDispatch = await executeCommandWithBoundedAwait(
      CURSOR_CREATE_NEW_COMPOSER_COMMAND,
      buildCursorCreateNewDraftArguments(message),
      commandAwaitTimeoutMs
    );
    if (createdDispatch.status === "pending") {
      return {
        ok: false,
        strategy: "command_create_new_composer",
        error: "cursor_create_new_composer_command_pending",
        pending_command: {
          command_id: CURSOR_CREATE_NEW_COMPOSER_COMMAND,
          timeout_ms: createdDispatch.timeout_ms
        },
        before_composer_ids: beforeComposerIds
      };
    }
    if (createdDispatch.status === "rejected") {
      return {
        ok: false,
        strategy: "command_create_new_composer",
        error: createdDispatch.error || "cursor_create_new_composer_command_rejected",
        command_error: {
          command_id: CURSOR_CREATE_NEW_COMPOSER_COMMAND,
          error: createdDispatch.error || "cursor_create_new_composer_command_rejected"
        },
        before_composer_ids: beforeComposerIds
      };
    }
    const created = createdDispatch.result;
    const afterComposerIds = collectComposerIdsFromHandle(handle);
    let createdComposerId = inferCreatedComposerId(created, beforeComposerIds, afterComposerIds);
    let createdHandle = null;
    if (!createdComposerId) {
      const candidates = uniqueStrings([...afterComposerIds, composerId]);
      for (const candidateId of candidates.slice(0, 8)) {
        const candidateHandle = await getComposerHandleSafe(candidateId, commandAwaitTimeoutMs);
        const candidateSummary = summarizeComposerHandle(candidateHandle, candidateId);
        if (composerSummaryContainsMessage(candidateSummary, message)) {
          createdComposerId = candidateId;
          createdHandle = candidateHandle;
          break;
        }
      }
    }
    if (!createdComposerId) {
      return {
        ok: false,
        strategy: "command_create_new_composer",
        error: "cursor_create_new_composer_missing_id",
        before_composer_ids: beforeComposerIds,
        after_composer_ids: afterComposerIds,
        created_result: summarizeCommandResult(created)
      };
    }
    if (!createdHandle) {
      createdHandle = await getComposerHandleSafe(createdComposerId, commandAwaitTimeoutMs);
    }
    return {
      ok: true,
      strategy: "command_create_new_composer",
      composer_id: createdComposerId,
      before_composer_ids: beforeComposerIds,
      after_composer_ids: afterComposerIds,
      created_result: summarizeCommandResult(created),
      after: summarizeComposerHandle(createdHandle, createdComposerId)
    };
  }
  if (handle && typeof handle.setData === "function") {
    handle.setData({
      text: message,
      richText: buildCursorPlainTextRichText(message)
    });
    return {
      ok: true,
      strategy: "handle_set_data"
    };
  }
  const state = findComposerState(handle, composerId);
  if (!state || typeof state !== "object" || !("text" in state || "richText" in state)) {
    return {
      ok: false,
      strategy: "none",
      error: "cursor_draft_state_unavailable"
    };
  }
  state.text = message;
  state.richText = buildCursorPlainTextRichText(message);
  if (typeof state._v === "number") {
    state._v += 1;
  }
  return {
    ok: true,
    strategy: "state_direct_patch"
  };
}

async function applyCursorLiveAttachDraftMutation(message, commandAwaitTimeoutMs) {
  const createdDispatch = await executeCommandWithBoundedAwait(
    CURSOR_CREATE_NEW_COMPOSER_COMMAND,
    buildCursorCreateNewDraftArguments(message),
    commandAwaitTimeoutMs
  );
  if (createdDispatch.status === "pending") {
    return {
      ok: false,
      strategy: "command_create_new_composer_live_attach",
      error: "cursor_create_new_composer_command_pending",
      pending_command: {
        command_id: CURSOR_CREATE_NEW_COMPOSER_COMMAND,
        timeout_ms: createdDispatch.timeout_ms
      }
    };
  }
  if (createdDispatch.status === "rejected") {
    return {
      ok: false,
      strategy: "command_create_new_composer_live_attach",
      error: createdDispatch.error || "cursor_create_new_composer_command_rejected",
      command_error: {
        command_id: CURSOR_CREATE_NEW_COMPOSER_COMMAND,
        error: createdDispatch.error || "cursor_create_new_composer_command_rejected"
      }
    };
  }
  const created = createdDispatch.result;
  return {
    ok: true,
    strategy: "command_create_new_composer_live_attach",
    composer_id: inferCreatedComposerId(created, [], []),
    created_result: summarizeCommandResult(created)
  };
}

function buildCursorCreateNewDraftArguments(message) {
  return [
    {
      unifiedMode: "agent",
      skipShowAndFocus: true,
      skipSelect: true,
      openInNewTab: false,
      partialState: {
        unifiedMode: "agent",
        text: message,
        richText: buildCursorPlainTextRichText(message)
      }
    }
  ];
}

function collectComposerIdsFromHandle(handle) {
  const loadedComposers = handle && handle.manager && handle.manager.loadedComposers;
  const values = [];
  if (handle && handle.composerId) {
    values.push(handle.composerId);
  }
  if (Array.isArray(loadedComposers && loadedComposers.ids)) {
    values.push(...loadedComposers.ids);
  }
  if (Array.isArray(loadedComposers && loadedComposers.store && loadedComposers.store.ids)) {
    values.push(...loadedComposers.store.ids);
  }
  if (loadedComposers && loadedComposers.byId && typeof loadedComposers.byId === "object") {
    values.push(...safeOwnPropertyNames(loadedComposers.byId));
  }
  if (loadedComposers && loadedComposers.store && loadedComposers.store.byId && typeof loadedComposers.store.byId === "object") {
    values.push(...safeOwnPropertyNames(loadedComposers.store.byId));
  }
  return uniqueStrings(values);
}

function inferCreatedComposerId(created, beforeComposerIds, afterComposerIds) {
  const directId = safeString(
    (created && typeof created === "string" ? created : "") ||
    (created && typeof created === "object" ? created.composerId : "")
  );
  if (directId) {
    return directId;
  }
  const beforeSet = new Set(beforeComposerIds);
  return afterComposerIds.find((item) => item && !beforeSet.has(item)) || "";
}

async function getComposerHandleSafe(composerId, commandAwaitTimeoutMs) {
  if (!composerId) {
    return null;
  }
  const dispatch = await executeCommandWithBoundedAwait(
    CURSOR_COMPOSER_HANDLE_COMMAND,
    [composerId],
    commandAwaitTimeoutMs
  );
  return dispatch.status === "resolved" ? dispatch.result : null;
}

function composerSummaryContainsMessage(summary, message) {
  if (!summary || !message) {
    return false;
  }
  return safeString(summary.text).includes(message) || safeString(summary.rich_text).includes(message);
}

function collectCursorHandleDiagnostics(handle, composerId) {
  const state = findComposerState(handle, composerId);
  const diagnostics = {
    handle_type: describeValueType(handle),
    state_type: describeValueType(state),
    top_level_keys: safeOwnPropertyNames(handle).filter((key) => typeof safeGet(handle, key) !== "function").slice(0, 80),
    top_level_function_keys: safeOwnPropertyNames(handle).filter((key) => typeof safeGet(handle, key) === "function").slice(0, 80),
    prototype_function_keys: collectPrototypeFunctionKeys(handle),
    state_keys: safeOwnPropertyNames(state).filter((key) => typeof safeGet(state, key) !== "function").slice(0, 80),
    state_function_keys: safeOwnPropertyNames(state).filter((key) => typeof safeGet(state, key) === "function").slice(0, 80),
    state_prototype_function_keys: collectPrototypeFunctionKeys(state),
    object_paths: [],
    write_method_candidates: []
  };
  const seen = new Set();
  collectCursorHandleDiagnosticsFromValue(handle, "handle", seen, diagnostics, 0);
  if (state && state !== handle) {
    collectCursorHandleDiagnosticsFromValue(state, "state", seen, diagnostics, 0);
  }
  diagnostics.object_paths = diagnostics.object_paths.slice(0, 80);
  diagnostics.write_method_candidates = diagnostics.write_method_candidates.slice(0, 80);
  return diagnostics;
}

function collectCursorHandleDiagnosticsFromValue(value, path, seen, diagnostics, depth) {
  if (!value || (typeof value !== "object" && typeof value !== "function")) {
    return;
  }
  if (seen.has(value) || depth > 4) {
    return;
  }
  seen.add(value);
  const keys = safeOwnPropertyNames(value).slice(0, 120);
  const objectEntry = {
    path,
    value_type: describeValueType(value),
    keys: [],
    function_keys: [],
    prototype_function_keys: collectPrototypeFunctionKeys(value).slice(0, 40)
  };
  for (const prototypeKey of objectEntry.prototype_function_keys) {
    const childPath = `${path}.<prototype>.${prototypeKey}`;
    if (isCursorWriteMethodCandidate(prototypeKey, childPath)) {
      diagnostics.write_method_candidates.push({
        function_path: childPath,
        name: prototypeKey
      });
    }
  }
  for (const key of keys) {
    const child = safeGet(value, key);
    const childPath = `${path}.${key}`;
    if (typeof child === "function") {
      objectEntry.function_keys.push(key);
      if (isCursorWriteMethodCandidate(key, childPath)) {
        diagnostics.write_method_candidates.push({
          function_path: childPath,
          name: key
        });
      }
      continue;
    }
    objectEntry.keys.push(key);
  }
  diagnostics.object_paths.push({
    ...objectEntry,
    keys: objectEntry.keys.slice(0, 40),
    function_keys: objectEntry.function_keys.slice(0, 40),
    prototype_function_keys: objectEntry.prototype_function_keys
  });
  for (const key of keys) {
    const child = safeGet(value, key);
    if (child && typeof child === "object") {
      collectCursorHandleDiagnosticsFromValue(child, `${path}.${key}`, seen, diagnostics, depth + 1);
    }
  }
}

function isCursorWriteMethodCandidate(name, functionPath) {
  const text = `${name} ${functionPath}`;
  return /setData|updateComposerData|updateComposerDataSetStore|setState|setText|draft|richText/i.test(text);
}

function collectPrototypeFunctionKeys(value) {
  if (!value || (typeof value !== "object" && typeof value !== "function")) {
    return [];
  }
  const selected = [];
  const seen = new Set();
  let current = value;
  for (let depth = 0; depth < 4; depth += 1) {
    current = Object.getPrototypeOf(current);
    if (!current || current === Object.prototype) {
      break;
    }
    for (const key of safeOwnPropertyNames(current)) {
      if (key === "constructor" || seen.has(key)) {
        continue;
      }
      if (typeof safeGet(current, key) === "function") {
        seen.add(key);
        selected.push(key);
      }
    }
  }
  return selected.slice(0, 80);
}

function safeOwnPropertyNames(value) {
  if (!value || (typeof value !== "object" && typeof value !== "function")) {
    return [];
  }
  try {
    return Object.getOwnPropertyNames(value);
  } catch (_error) {
    return [];
  }
}

function safeGet(value, key) {
  try {
    return value && value[key];
  } catch (_error) {
    return undefined;
  }
}

function describeValueType(value) {
  if (value === null) {
    return "null";
  }
  if (Array.isArray(value)) {
    return "array";
  }
  return typeof value;
}

function findComposerState(handle, composerId) {
  if (!handle || typeof handle !== "object") {
    return null;
  }
  const loadedComposers = handle.manager && handle.manager.loadedComposers;
  const candidates = [
    handle,
    handle.byId && handle.byId[composerId],
    handle.data && handle.data.byId && handle.data.byId[composerId],
    handle._data && handle._data.byId && handle._data.byId[composerId],
    handle.manager && handle.manager.byId && handle.manager.byId[composerId],
    handle.manager && handle.manager.data && handle.manager.data.byId && handle.manager.data.byId[composerId],
    handle.manager && handle.manager._data && handle.manager._data.byId && handle.manager._data.byId[composerId],
    loadedComposers && loadedComposers.byId && loadedComposers.byId[composerId],
    loadedComposers && loadedComposers.store && loadedComposers.store.byId && loadedComposers.store.byId[composerId]
  ];
  return candidates.find((item) => isComposerStateLike(item, composerId)) || null;
}

function isComposerStateLike(value, composerId) {
  if (!value || typeof value !== "object") {
    return false;
  }
  if (composerId && value.composerId && value.composerId !== composerId) {
    return false;
  }
  return (
    typeof value.text === "string" ||
    typeof value.richText === "string" ||
    (value.conversationMap && typeof value.conversationMap === "object") ||
    Array.isArray(value.subComposerIds) ||
    Object.prototype.hasOwnProperty.call(value, "isDraft")
  );
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

function buildChatCommandArguments(commandId, message, payload, metadata, adapterId) {
  if (commandId === "workbench.action.chat.open") {
    return [{ query: message }];
  }
  return [
    {
      message,
      target: payload.target || {},
      metadata: {
        ...metadata,
        adapter_id: adapterId,
        command_id: commandId
      }
    }
  ];
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

function uniqueStrings(values) {
  const selected = [];
  const seen = new Set();
  if (!Array.isArray(values)) {
    return selected;
  }
  for (const value of values) {
    const item = typeof value === "string" ? value.trim() : "";
    if (!item || seen.has(item)) {
      continue;
    }
    selected.push(item);
    seen.add(item);
  }
  return selected;
}

function safeString(value) {
  return typeof value === "string" ? value : "";
}

function buildCursorPlainTextRichText(text) {
  return JSON.stringify({
    root: {
      children: [
        {
          children: [
            {
              detail: 0,
              format: 0,
              mode: "normal",
              style: "",
              text,
              type: "text",
              version: 1
            }
          ],
          format: "",
          indent: 0,
          type: "paragraph",
          version: 1
        }
      ],
      format: "",
      indent: 0,
      type: "root",
      version: 1
    }
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
    bridge_url: serverAddress,
    bridge_state_file: serverStatePath,
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
