import os

def get_unique_path(path):
    if not os.path.exists(path):
        return path
    i = 1
    while True:
        name, ext = os.path.splitext(path)
        new_path = f"{name} ({i}){ext}"
        if not os.path.exists(new_path):
            return new_path
        i += 1

def get_unique_dir_path(path):
    if not os.path.exists(path):
        return path
    i = 1
    while True:
        new_path = f"{path} ({i})"
        if not os.path.exists(new_path):
            return new_path
        i += 1