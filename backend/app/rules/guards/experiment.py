from app.rules.context import RuleContext


def check_experiment(context: RuleContext, action: str) -> tuple:
    if not context.active_experiments:
        return True, None
    variable_actions = {"REVIEW_SCALE", "REVIEW_REDUCE_BUDGET", "REVIEW_PAUSE", "REFRESH_CREATIVE"}
    if action in variable_actions:
        return False, "EXPERIMENT_PROTECTION"
    return True, None
