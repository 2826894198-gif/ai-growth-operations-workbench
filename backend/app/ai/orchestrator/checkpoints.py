from langgraph.checkpoint.memory import MemorySaver


def build_checkpointer():
    """Checkpoint store for the graph.

    Dev default is an in-memory saver (thread-level resume within the process).
    PostgreSQL-backed persistence is a documented deferred item for production.
    """
    return MemorySaver()
