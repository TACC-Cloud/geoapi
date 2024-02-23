def get_api_server(tenant_name):
    # todo - lookup tenant in tenants table
    if tenant_name.upper() == 'PORTALS':
        return 'https://portals.tapis.io'
    if tenant_name.upper() == 'DESIGNSAFE':
        return 'https://designsafe.tapis.io'
    raise Exception(f"API server not found for tenant:{tenant_name}")


def get_service_accounts(tenant_name):
    service_accounts = {"DESIGNSAFE": ["prjadmin", "ds_admin"]}
    return service_accounts.get(tenant_name.upper(), [])
