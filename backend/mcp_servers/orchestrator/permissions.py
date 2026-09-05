"""Permission classification for orchestrated tool calls.

This is a thin policy layer, not a second approval queue. The one real
approval queue in this codebase is
app.services.fulfillment.workflow.FulfillmentWorkflowEngine (WAITING_APPROVAL
/ approve_workflow / reject_workflow) — mcp_servers/amazon/server.py's
create_order tool already routes every order through it and never
auto-approves. Nothing here duplicates that state machine.

What this module adds is a call-time gate in front of the orchestrator's
`call_tool`: writes are never executed silently just because an agent asked
for them. A write tool call must be made with `confirmed=True` (an explicit,
one-call acknowledgement — not a stored approval) or client_manager refuses
it and explains why. This is deliberately simpler than the fulfillment
workflow's queue: it exists only to stop an agent from firing off a mutating
call it didn't mean to, not to model a multi-step human review process —
create_order's *actual* approval gate is the fulfillment workflow, reached
after this layer lets the call through.
"""

# Read-only tool name prefixes — safe to call without confirmation.
SAFE_PREFIXES = ("get_", "check_", "read_", "list_", "find_")

# Tools that mutate state and always require `confirmed=True`, beyond what
# the SAFE_PREFIXES heuristic alone would catch (e.g. update_fulfillment
# doesn't start with a safe prefix, so it's already covered — listed
# explicitly anyway so the policy doesn't silently depend on naming alone).
EXPLICIT_CONFIRMATION_REQUIRED: frozenset[str] = frozenset(
    {"create_order", "update_fulfillment", "append_row", "update_row"}
)

# Tools whose real safety gate is the fulfillment approval workflow itself
# (see module docstring) — flagged separately so callers/UIs can explain
# *why* this one is different from a plain "are you sure" confirmation.
ROUTES_THROUGH_FULFILLMENT_APPROVAL: frozenset[str] = frozenset({"create_order"})


def is_safe(tool_name: str) -> bool:
    """Whether a tool is read-only and safe to call without confirmation."""
    if tool_name in EXPLICIT_CONFIRMATION_REQUIRED:
        return False
    return tool_name.startswith(SAFE_PREFIXES)


def requires_confirmation(tool_name: str) -> bool:
    """Whether client_manager.call_tool must see confirmed=True for this tool.

    Unknown tool names (not matching a safe prefix, not explicitly listed)
    are treated as requiring confirmation too — safe-by-default, since a new
    tool added to a child server without an explicit safety review should
    never silently become freely callable.
    """
    return not is_safe(tool_name)
