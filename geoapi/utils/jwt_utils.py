from typing import Dict


def jwt_tenant(headers: Dict) -> (str, str, str):
    """
    Extract the tenant info from the headers
    :param headers: Dict
    :return: (jwt_header_name: str, jwt_header: str, tenant_name: str
    """
    for k, v in headers.items():
        if k.lower().startswith('x-jwt-assertion-'):
            tenant_name = k.lower().split('x-jwt-assertion-')[1]
            jwt_header_name = k
            jwt = v
            return jwt_header_name, jwt, tenant_name
    else:
        raise ValueError("No JWT could be found")