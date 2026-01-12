
import contextvars

# Context variable to store the current user ID
# This allows logs generated deep in the call stack to know which user they belong to
user_id_var = contextvars.ContextVar("user_id", default=None)
