import types
from sh import Command
import importlib
from rich import print as rprint


def loudspeaker(some_command):
    def stream_and_capture_output(line, buffer):
        rprint(line, end='')  # Stream the output in real-time
        buffer.append(line)  # Append the output to a list
    def run_command(*args, **kwargs):
        output_buffer = []
        def stream_and_capture_line(line):
            stream_and_capture_output(line, output_buffer)
        kwargs['_out'] = stream_and_capture_line
        kwargs['_err'] = stream_and_capture_line
        some_command(*args, **kwargs)
        return ''.join(output_buffer)  # Return the captured output as a string
    return run_command

def wrap_module_with_decorator(module_name, decorator):
    # Import the target module dynamically
    original_module = importlib.import_module(module_name)

    # Create a wrapper module
    wrapped_module = types.ModuleType(module_name)

    # Iterate over the attributes of the original module
    for attr_name in dir(original_module):
        attr = getattr(original_module, attr_name)
        # Apply the decorator if the attribute is callable
        if callable(attr):
            setattr(wrapped_module, attr_name, decorator(attr))
        else:
            setattr(wrapped_module, attr_name, attr)

    return wrapped_module