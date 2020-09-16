import subprocess
import re
import traceback
import sys
import os
import platform
import json
from datetime import datetime,date,timezone

dep_lib_re1 = re.compile("^(?P<name>[a-zA-Z0-9_\-]+)\s*\[\s*required\:\s*(?P<required>.+)\s*\,\s*installed:\s*(?P<installed>[\S]+)\s*\]$",re.IGNORECASE)
dep_lib_re2 = re.compile("^(?P<name>[a-zA-Z0-9_\-]+)\s*==\s*(?P<version>[\S]+)$",re.IGNORECASE)

def is_installed(lib,pip="pip"):
    """
    check whether libraray is installed or not 
    """
    try:
        subprocess.check_call("{} show {}".format(pip,lib),shell=True)
        return True
    except:
        return False

def harvest():
    with open("/image_metadata.json",'r') as f:
        metadata = json.loads(f.read())

    installed_by_harvester = set()
    for name,lib in (("pipdeptree","pipdeptree"),("distro","distro==1.5.0")):
        if not is_installed(name,metadata.get("image_pip","pip")):
            try:
                subprocess.check_call("{} install {}".format(metadata.get("image_pip","pip"),lib),shell=True)
            except :
                trackback.print_exc()

            if not is_installed(name,metadata.get("image_pip","pip")):
                raise Exception("Install library({}) failed".format(name))

            print("The library({}) is installed by harvester".format(name))
            installed_by_harvester.add(name)

    import distro

    #get os information
    metadata["image_platform"] = sys.platform
    os_release_name = None
    os_version = None
    os_name = None
    os_dist = distro.linux_distribution(full_distribution_name=True)
    if len(os_dist) >= 3:
        os_release_name = os_dist[2]

    if len(os_dist) >= 2:
        os_version = os_dist[1]

    if len(os_dist) >= 1:
        os_name = os_dist[0]

    metadata["image_os"] = os_name
    metadata["image_os_version"] = os_version
    metadata["image_os_release_name"] = os_release_name

    if metadata.get("app_language") == "python":
        metadata["app_language_major_version"] = sys.version_info[0]
        metadata["app_language_version"] = "{}.{}.{}".format(*sys.version_info[0:3])
    
    #pip dependency tree
    if metadata["app_language"] == "python":
        dependency_data = subprocess.check_output("pipdeptree",shell=True).decode()
        dependency_lines = dependency_data.split(os.linesep)
        deptree = []
        level_stack=[]
        for line in dependency_lines:
            if not line.strip():
                #empty line
                continue
            if line.strip()[0] == '-':
                dep_level,dep_lib = line.split("-",maxsplit=1)
                dep_level = len(dep_level)
            else:
                dep_level = 0
                dep_lib = line
            dep_lib = dep_lib.strip()
            m = dep_lib_re1.search(dep_lib)
            if not m:
                m = dep_lib_re2.search(dep_lib)
                if m:
                    lib = m.group("name")
                    lib_ver_required = m.group("version")
                    lib_ver_installed = m.group("version")
                else:
                    raise Exception("Failed to parse the python library dependency({})".format(dep_lib))
            else:
                lib = m.group("name")
                lib_ver_required = m.group("required")
                lib_ver_installed = m.group("installed")
            lib_dep_subtree = [lib,lib_ver_required,lib_ver_installed]

            if dep_level == 0:
                #top leve dependent tree
                level_stack.clear()
                deptree.append(lib_dep_subtree)
                level_stack.append((dep_level,lib_dep_subtree))
            elif dep_level == level_stack[-1][0]:
                #same dependent level as the last dependent lib
                #last dependent lib has no dependent lib
                level_stack.pop()
                if len(level_stack[-1][1]) == 3:
                    level_stack[-1][1].append([lib_dep_subtree])
                else:
                    level_stack[-1][1][3].append(lib_dep_subtree)
            elif dep_level > level_stack[-1][0]:
                #the dependent level is deeper than the last dependent lib,
                #current lib is dependent by the last dependent lib
                if len(level_stack[-1][1]) == 3:
                    level_stack[-1][1].append([lib_dep_subtree])
                else:
                    level_stack[-1][1][3].append(lib_dep_subtree)
                level_stack.append((dep_level,lib_dep_subtree))
            else:
                #the dependent level is less than the last dependent lib,
                #find the lib which is depenent this lib directly
                while level_stack[-1][0] >= dep_level:
                    level_stack.pop()

                if len(level_stack[-1][1]) == 3:
                    level_stack[-1][1].append([lib_dep_subtree])
                else:
                    level_stack[-1][1][3].append(lib_dep_subtree)
                level_stack.append((dep_level,lib_dep_subtree))

        if not installed_by_harvester:
            index = len(deptree) - 1
            while index >= 0:
                try:
                    if deptree[index][0] in installed_by_harvester:
                        #pipdeptree is installed by harvester, remove it from dependency
                        del deptree[index]
                finally:
                    index -= 1

        metadata["image_python_dependent_tree"] = deptree

    with open("/image_metadata.json",'w') as f:
        f.write(json.dumps(metadata,indent=4))


if __name__ == "__main__":
    harvest()

