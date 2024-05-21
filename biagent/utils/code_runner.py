def safe_exec_func(code_string: str, param_space=None):
    param_space = {}
    # TODO: make sure the code is safe to execute
    exec(code_string, param_space)
    return param_space
