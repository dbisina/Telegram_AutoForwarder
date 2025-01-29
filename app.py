import subprocess

process1 = subprocess.Popen(["python", "bot_ui.py"])
process2 = subprocess.Popen(["python", "forwarder.py"])

process1.wait()
process2.wait()