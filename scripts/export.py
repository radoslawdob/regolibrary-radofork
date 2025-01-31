import json
import csv
import os
import subprocess as s
from pathlib import Path
import copy

"""
Export rules controls and frameworks to files in json format
"""
currDir = os.path.abspath(os.getcwd())

control_rule_rows = []
framework_control_rows = []

SUBSECTION_TREE_SEPARATOR = '.'

def ignore_file(file_name: str):
    return file_name.startswith('__')

def load_rules():
    p1 = os.path.join(currDir, 'rules') 
    regofile = 'raw.rego'
    filterregofile = 'filter.rego'
    rules_path = Path(p1).glob('**/*.json')
    loaded_rules = {}  # rules loaded from file system
    rules_list = []

    for path in rules_path:
        if ignore_file(path.parent.name):
            continue
        path_in_str = str(path)
        with open(path_in_str, "r") as f:
            new_rule = json.load(f)
        with open(os.path.join(os.path.dirname(path),regofile), 'r') as f:
            rule = f.read()
            if new_rule:
                new_rule["rule"] = rule
                try:
                    with open(os.path.join(os.path.dirname(path),filterregofile), 'r') as f:
                        filter_rego = f.read()
                        new_rule["resourceEnumerator"] = filter_rego
                except:
                    pass
        rules_list.append(new_rule)
        loaded_rules[new_rule['name']] = new_rule

    return loaded_rules, rules_list


def load_controls(loaded_rules: dict):
    p2 = os.path.join(currDir, 'controls') 
    controls_path = Path(p2).glob('**/*.json')
    loaded_controls = {}
    controls_list = []

    for path in controls_path:
        if ignore_file(path.name):
            continue
        path_in_str = str(path)

        with open(path_in_str, "r") as f:
            new_control = json.load(f)
        new_control["rules"] = []
        new_control_copy = copy.deepcopy(new_control)
        controls_list.append(new_control_copy)

        for rule_name in new_control["rulesNames"]:
            if rule_name in loaded_rules:
                new_control["rules"].append(loaded_rules[rule_name])
                new_row = [new_control['id'], rule_name] # TODO : change 'id' to 'controlID'
                control_rule_rows.append(new_row)
            else:
                raise Exception("Error in ruleNames of control {}, rule {} does not exist".format(new_control["name"], rule_name))

        del new_control["rulesNames"]  # remove rule names list from dict
        loaded_controls[new_control['name']] = new_control

    return loaded_controls, controls_list


def addSubsectionsIds(parents: list, sections: dict):
    '''
    Recursively iterate over framework subsection and adds the tree info as `id` attribute to the section
    '''
    for section_id, section in sections.items():
        section_full_id = parents.copy()
        section_full_id.append(section_id)
        section['id'] = SUBSECTION_TREE_SEPARATOR.join(section_full_id)
        addSubsectionsIds(section_full_id, section.get('subSections', {}))


def load_frameworks(loaded_controls: dict):
    p3 = os.path.join(currDir, 'frameworks') 
    frameworks_path = Path(p3).glob('**/*.json')
    loaded_frameworks = {}
    frameworks_list = []

    for path in frameworks_path:
        if ignore_file(path.name):
            continue
        path_in_str = str(path)
        with open(path_in_str, "r") as f:
            new_framework = json.load(f)
        new_framework["version"] = os.getenv("RELEASE")
        new_framework["controls"] = []
        new_framework_copy = copy.deepcopy(new_framework)
        frameworks_list.append(new_framework_copy)

        for control_name in new_framework["controlsNames"]:
            if control_name in loaded_controls:
                new_framework["controls"].append(loaded_controls[control_name])
                new_row = [new_framework['name'], loaded_controls[control_name]['id'], control_name] # TODO : change 'id' to 'controlID'
                framework_control_rows.append(new_row)
            else:
                raise Exception("Error in controlsNames of framework {}, control {} does not exist".format(new_framework["name"], control_name))
        
        addSubsectionsIds([], new_framework.get('subSections', {}))

        del new_framework["controlsNames"]
        loaded_frameworks[new_framework['name']] = new_framework

    return loaded_frameworks, frameworks_list


def load_attack_tracks():
    p3 = os.path.join(currDir, 'attack-tracks')
    attack_tracks_path = Path(p3).glob('**/*.json')
    loaded_attack_tracks = {}

    for path in attack_tracks_path:
        if ignore_file(path.name):
            continue
        path_in_str = str(path)
        with open(path_in_str, "r") as f:
            new_attack_track = json.load(f)
        new_attack_track["spec"]["version"] = os.getenv("RELEASE")
        loaded_attack_tracks[new_attack_track['metadata']['name']] = new_attack_track

    return list(loaded_attack_tracks.values())


def validate_controls():
    p4 = os.path.join(currDir, 'controls') 
    controls_path = list(Path(p4).glob('**/*.json'))
    set_of_ids = set()

    for path in  controls_path:
        path_in_str = str(path)

        with open(path_in_str, "r") as f:
            new_control = json.load(f)
        
        set_of_ids.add(new_control["id"])

    sum_of_controls = len(controls_path)
    if sum_of_controls != len(set_of_ids):
        raise Exception("Error validate the numbers of controls, {} != {}".format(sum_of_controls ,len(set_of_ids)))

def load_default_config_inputs():
    default_filename = "default-config-inputs"
    p5 = os.path.join(currDir, default_filename + ".json")
    with open(p5, "r") as f:
        config_inputs = json.load(f)
    return config_inputs


def validate_exceptions(exceptions):
    for exception in exceptions:
        if not "name" in exception or exception["name"] == "":
            raise Exception("Error in exception. Invalid exception object - missing name")
        name = exception["name"]

        # validate system exception attribute found
        attributes = exception.get("attributes", {})
        if not attributes.get("systemException", False):
            raise Exception(f"Error in exception '{name}'. expected 'systemException' attribute: {exception}")

        if not "resources" in exception:
            raise Exception(f"Error in exception '{name}'. Invalid exception object - missing resources filed")

        if not "posturePolicies" in exception:
            raise Exception(f"Error in exception '{name}'. Invalid exception object - missing posturePolicies filed")


def split_exceptions(exceptions):
    splitted_exceptions = []
    for exception in exceptions:
        if "resources" in exception and len(exception["resources"]) > 1:
            for i, resource in enumerate(exception["resources"]):
                tmp_exception = copy.deepcopy(exception)
                tmp_exception["resources"] = [resource]
                tmp_exception["name"] = f"{tmp_exception['name']}-{i}"
                splitted_exceptions.append(tmp_exception)
        else:
            splitted_exceptions.append(copy.deepcopy(exception))
    return splitted_exceptions
        

def load_exceptions():
    exceptions = os.path.join(currDir, 'exceptions')
    exceptions_path = Path(exceptions).glob('**/*.json')
    loaded_exceptions = []

    for path in exceptions_path:
        if ignore_file(path.name):
            continue
        path_in_str = str(path)
        with open(path_in_str, "r") as f:
            exceptions = json.load(f)
        
        if not isinstance(exceptions, list):
            raise Exception("Exceptions file {} is not a list".format(path_in_str))
        loaded_exceptions.extend(exceptions)

    # We split the exceptions this way we wont have large exceptions objects
    splitted_exceptions = split_exceptions(loaded_exceptions)

    # Validate exceptions object
    validate_exceptions(splitted_exceptions)
    return splitted_exceptions


def export_json(data: dict, f_name:str, output_path: str):
    os.makedirs(output_path, exist_ok=True)
    with open(os.path.join(output_path, f"{f_name.lower()}.json"), "w") as f:
        f.write(json.dumps(data, indent=4))


def create_cvs_file(header, rows, filename, output_path):
    os.makedirs(output_path, exist_ok=True)
    with open(os.path.join(output_path, f"{filename}.csv"), 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


if __name__ == '__main__':
    output_dir_name = os.getenv("OUTPUT") if os.getenv("OUTPUT") else "release"

    loaded_rules, rules_list = load_rules()   
    rules, rules_list = load_rules()
    controls, controls_list = load_controls(loaded_rules=rules)
    validate_controls()
    frameworks, frameworks_list = load_frameworks(loaded_controls=controls)
    default_config_inputs = load_default_config_inputs()
    attack_tracks_list = load_attack_tracks()
    exceptions_list = load_exceptions()

    # create full framework json files
    # TODO - delete when kubescape works with csv files
    for k, v in frameworks.items():
        export_json(data=v, f_name=k, output_path=output_dir_name)

    # create object json's - frameworks, controls, rules
    export_json(frameworks_list, 'frameworks', output_dir_name)
    export_json(controls_list, 'controls', output_dir_name)
    export_json(rules_list, 'rules', output_dir_name)
    export_json(default_config_inputs, 'default_config_inputs', output_dir_name)
    export_json(attack_tracks_list, 'attack_tracks', output_dir_name)
    export_json(exceptions_list, 'exceptions', output_dir_name)

    # file 1 - 'ControlID', 'RuleName'
    header1 = ['ControlID', 'RuleName']
    create_cvs_file(header1, control_rule_rows, 'ControlID_RuleName', output_dir_name)

    # file 2 - frameworkName, ControlID, ControlName
    header2 = ['frameworkName', 'ControlID', 'ControlName']
    create_cvs_file(header2, framework_control_rows, 'FWName_CID_CName', output_dir_name)
