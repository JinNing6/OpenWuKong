# -*- coding: utf-8 -*-
"""Connector registry and selection logic."""

from __future__ import annotations

from typing import Iterable, Optional

from openwukong.connectors.base import ConnectorTarget, SessionConnector


class ConnectorManager:
    """Selects the best connector for a given target."""

    def __init__(self, connectors: Optional[Iterable[SessionConnector]] = None):
        self._connectors: list[SessionConnector] = list(connectors or [])

    def register(self, connector: SessionConnector):
        self._connectors.append(connector)

    def list_connector_ids(self) -> list[str]:
        return [connector.connector_id for connector in self._connectors]

    def resolve_session_connector(
        self,
        target: ConnectorTarget,
        preferred: str = "",
        enforce_route_policy: bool = False,
        route_plan: object = None,
    ) -> SessionConnector:
        if enforce_route_policy:
            plan = route_plan
            if plan is None:
                from openwukong.connectors.route_policy import build_control_route_plan

                plan = build_control_route_plan(target)
            if getattr(plan, "is_blocked", False):
                primary_route = getattr(getattr(plan, "primary_route", None), "route_id", "")
                decision = getattr(plan, "control_decision", "")
                raise PermissionError(
                    "route_policy_blocked: "
                    f"process={target.process_name!r} title={target.window_title!r} "
                    f"primary_route={primary_route!r} decision={decision!r}"
                )

        preferred = (preferred or "").strip().lower()
        if preferred and preferred != "auto":
            for connector in self._connectors:
                if connector.connector_id.lower() == preferred:
                    return connector

        best_connector: Optional[SessionConnector] = None
        best_score = -1
        for connector in self._connectors:
            score = connector.match_score(target)
            if score > best_score:
                best_score = score
                best_connector = connector

        if best_connector is not None and best_score >= 0:
            return best_connector

        raise LookupError(
            f"No connector available for pid={target.pid} process={target.process_name!r}"
        )
