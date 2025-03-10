import json

#Easily convert the old JSON format to the new agent configuration format

def migrate_old_to_new(old_json, conversion_type="legacy"):
    new_json = {
        "config": {
            "name": old_json["name"],
            "type": conversion_type,
            "loop_delay": old_json["loop_delay"],
        },
        "llms": {
            "character": {
                "name": old_json["name"],
                "bio": old_json["bio"],
                "traits": old_json["traits"],
                "examples": old_json["examples"],
                "example_accounts": old_json["example_accounts"],
                "model_provider": "openai",
                "model": "gpt-3.5-turbo",
            }
        },
        "connections": [],
    }

    if conversion_type == "autonomous":
        new_json["llms"]["executor"] = {
            "model_provider": "openai",  # openai or anthropic for langchain
            "model": "gpt-4o-mini",
        }
    else:
        new_json["config"]["time_based_multipliers"] = old_json["time_based_multipliers"]
        new_json["tasks"] = old_json.get("tasks", [])

    new_json["connections"] = [
        {"name": item["name"], "config": {k: v for k, v in item.items() if k != "name"}}
        for item in old_json["config"]
    ]

    return new_json

def migrate_config(agent_file_name,agent_type):
    with open("agents/{}.json".format(agent_file_name), "r") as f:
        old_data = json.load(f)

    new_data = migrate_old_to_new(old_data, agent_type)

    # Save new JSON to a file
    new_file_name = "agents/{}-migrated.json".format(agent_file_name)
    with open(new_file_name, "w") as f:
        json.dump(new_data, f, indent=2)

    print("Migration complete. New agent configuration of type {} saved to {}".format(agent_type,new_file_name))
