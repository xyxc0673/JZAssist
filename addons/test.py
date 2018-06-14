import os
running_path = os.path.dirname(__file__)
path = os.path.join(running_path + "/answer.txt")
with open(path, "r") as f:
	print(f.read())