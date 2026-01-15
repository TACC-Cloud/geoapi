from tapipy.tapis import Tapis
import getpass
import requests
import logging

logging.basicConfig(
    level=logging.INFO,  # Set the minimum log level to INFO
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

def get_laz_files(paths):
    all_laz_files = []

    for directory_path in paths:
        laz_files = []
        offset = 0
        file_limit = 1000

        while True:
            files = t.files.listFiles(systemId=system_id, path=directory_path, limit=file_limit, offset=offset)

            laz_files.extend([file for file in files if file.path.endswith('.laz')])

            if len(files) < file_limit:
                break

            # Increment the offset to fetch the next batch of files
            offset += file_limit

        # Print the total number of files found in the directory
        logging.info(f"Total .laz files in '{directory_path}': {len(laz_files)}")

        all_laz_files.extend(laz_files)

    laz_files_sorted = sorted(all_laz_files, key=lambda file: file.size)
    logging.info(
        f"Total number of .laz files is {len(laz_files_sorted)}. from {laz_files_sorted[0].size} to {laz_files_sorted[-1].size} bytes")

    # sort again by name
    laz_files_sorted = sorted(all_laz_files, key=lambda file: file.name)
    return laz_files_sorted


def get_laz_files_not_completed(jwt, map_project_id, laz_files, redo_failed=True):
    response = requests.get(
        f'{HAZMAPPER_BACKEND}/projects/{map_project_id}/point-cloud/',
        headers={'X-Tapis-Token': jwt}
    )
    response.raise_for_status()
    point_cloud_list = response.json()

    point_clouds = {pc["description"]: pc for pc in point_cloud_list}

    laz_files_todo = []
    for laz in laz_files:
        if laz.path in point_clouds:
            status = point_clouds[laz.path]["task"]["status"]
            description = point_clouds[laz.path]["task"]["description"]
            if status == "FINISHED":
                # skipping as assumed done done
                pass
            else:
                logging.error(f"Problem with {laz.path}.  status={status} description={description}.  need to fix! "
                              f" Deleting point cloud and adding to list to do")
                logging.error(f"Problem with {laz.path}.  status={status} description={description}.  need to fix! "
                              f" skipping.")
                continue
                try:
                    response = requests.delete(
                        f'{HAZMAPPER_BACKEND}/projects/{map_project_id}/point-cloud/{point_clouds[laz.path]["id"]}/',
                        headers={'X-Tapis-Token': jwt}
                    )
                    response.raise_for_status()
                    laz_files_todo.append(laz)
                except:
                    logging.exception(f"Issue deleting point cloud ({point_clouds[laz.path]['id']}) for : {laz.path}; won't retry")
                    raise
        else:
            # just do ones we haven't tried yet
            logging.info(f"Have not yet done {laz.path} (size={laz.size} so adding to list to do")
            laz_files_todo.append(laz)
    return laz_files_todo


def create_point_cloud_feature(jwt, map_project_id, system_id, laz_file):
    try:
        logging.info(f"Creating point cloud for : {laz_file.path}")
        data = {'description': laz_file.path}
        response = requests.post(
            f'{HAZMAPPER_BACKEND}/projects/{map_project_id}/point-cloud/',
            json=data,
            headers={'X-Tapis-Token': jwt}
        )
        response.raise_for_status()
        point_cloud_id = response.json()["id"]

        response = requests.post(
            f'{HAZMAPPER_BACKEND}/projects/{map_project_id}/point-cloud/{point_cloud_id}/import/',
            json={"files": [{"system": system_id, "path": laz_file.path}]},
            headers={'X-Tapis-Token': jwt})

        response.raise_for_status()
    except:
        logging.exception(f"Issue creating point cloud for : {laz_file.path}")


if __name__ == "__main__":
    # Target map is associated with this project:
    # PRJ-4211
    # map was created by UWRAPID:
    # https://hazmapper.tacc.utexas.edu/hazmapper/project-public/7073c5aa-3ec8-499d-99ac-11548709a54f
    map_project_id = 1022
    
    # TEST map is https://hazmapper.tacc.utexas.edu/hazmapper/project/a0559e4f-08a8-4f0d-920d-9099a538617e
    # map_project_id = 1230 TEST MAP

    # Hurricane Ian
    system_id = "project-7484001337096999406-242ac117-0001-012"
    paths = ["/2_Processing/FixedCSTiles"]
    
    username = input("Enter your username: ")
    password = getpass.getpass("Enter your password: ")

    HAZMAPPER_BACKEND = "https://hazmapper.tacc.utexas.edu/geoapi"

    # Create python Tapis client for user
    t = Tapis(base_url="https://designsafe.tapis.io",
              username=username,
              password=password)
    t.get_tokens()
    jwt = t.access_token.access_token

    laz_files = get_laz_files(paths)
    laz_files_todo = get_laz_files_not_completed(jwt=jwt, map_project_id=map_project_id, laz_files=laz_files)
    logging.info(f"Identified {len(laz_files_todo)} .laz files to process")
    laz_files_todo = laz_files_todo[:100]
    logging.info(f"Doing {len(laz_files_todo)} .laz files ")
    for l in laz_files_todo:
        create_point_cloud_feature(jwt=jwt, map_project_id=map_project_id, system_id=system_id, laz_file=l)
        import time
        time.sleep(25)
