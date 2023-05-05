import geoapi_client
from geoapi_client.rest import ApiException
import concurrent.futures
import os

TOKEN = os.environ['TOKEN']
EXAMPLE_FILE = {"files": [{"path": "/3_Deliverables/Safeway Supermarket/Pointclouds/TLS/LAZ_combined/Safeway_combined_3cm_20190329.laz", "system": "project-159846449346309655-242ac119-0001-012"}]}
configuration = geoapi_client.Configuration()
configuration.host = "https://agave.designsafe-ci.org/geo/v2"
configuration.api_key_prefix['Authorization'] = 'Bearer'
configuration.api_key['Authorization'] = TOKEN

api_client = geoapi_client.ApiClient(configuration)
api_instance = geoapi_client.ProjectsApi(api_client=api_client)

def create_point_cloud_and_import_file(project_id, index):
    point_cloud = api_instance.add_point_cloud(project_id=project_id, payload={"description": f"point_cloud{index}", "files_info": "dummy" })
    point_cloud_importing = api_instance.import_point_cloud_file_from_tapis(project_id=project.id, point_cloud_id=point_cloud.id, payload=EXAMPLE_FILE)
    print(f"submitted: {index} {point_cloud_importing}")
    return index, point_cloud_importing

try:
    test_id = "Testing multiple point cloud load"
    project = api_instance.create_project(payload={"project": {"name": f"My project {test_id}"}})
    project_id = project.id
    workers = 20
    number_of_point_clouds=100
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        importing_point_cloud_futures = [executor.submit(create_point_cloud_and_import_file, project_id, index) for index in list(range(1, number_of_point_clouds))]

        results = []
        for future in concurrent.futures.as_completed(importing_point_cloud_futures):
            index, result = future.result()
        results.append(result)
        print(results)
except ApiException as e:
    print("Exception: %s\n" % e)






