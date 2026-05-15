import json

with open("positions.json") as f:
    data = json.load(f)

pos_id = "1"
pos = data["positions"][pos_id]

j1 = pos["joints"]["joint1"]
j2 = pos["joints"]["joint2"]
j3 = pos["joints"]["joint3"]
grip = pos["gripper"]

move_stepper(j1, joint1)
move_stepper(j2, joint2)
move_stepper(j3, joint3)

if grip == "open":
    gripper.open()
else:
    gripper.close()