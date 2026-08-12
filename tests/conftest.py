import os
# Force background tasks off in test environment to prevent locks
os.environ["DISABLE_BACKGROUND_TASKS"] = "True"
