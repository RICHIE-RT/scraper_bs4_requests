import json
from config.team import names


def write_json(file_name: str, data: dict|list, mode="w", indent=4):
    with open(f"testing_data/{file_name}.json", mode) as data_file:
        json.dump(data, data_file, indent=indent)


def restructured_addtional_sub_details(details: list[dict]):
    new_details = dict()
    for detail in details:
        for key, value in detail.items():
            if key == "name": continue
            if key not in new_details.keys():
                new_details[key] = [{"type": value}]
                new_details[key][0]["name"] = detail["name"]
            else:
                new_details[key].append({"type": value})
                new_details[key][1]["name"] = detail["name"]
    return new_details