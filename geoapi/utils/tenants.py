def get_api_server(tenant_name):
    # todo - lookup tenant in tenants table
    if tenant_name.upper() == 'AGAVE-PROD':
        return 'https://public.agaveapi.co'
    if tenant_name.upper() == 'ARAPORT-ORG':
        return 'https://api.araport.org'
    if tenant_name.upper() == 'DESIGNSAFE':
        return 'https://agave.designsafe-ci.org'
    if tenant_name.upper() == 'DEV-STAGING':
        return 'https://dev.tenants.staging.tacc.cloud'
    if tenant_name.upper() == 'DEV-DEVELOP':
        return 'https://dev.tenants.develop.tacc.cloud'
    if tenant_name.upper() == 'IPLANTC-ORG':
        return 'https://agave.iplantc.org'
    if tenant_name.upper() == 'IREC':
        return 'https://irec.tenants.prod.tacc.cloud'
    if tenant_name.upper() == 'TACC-PROD':
        return 'https://api.tacc.utexas.edu'
    if tenant_name.upper() == 'SD2E':
        return 'https://api.sd2e.org'
    if tenant_name.upper() == '3DEM':
        return 'https://api.3dem.org'
    if tenant_name.upper() == 'SGCI':
        return 'https://agave.sgci.org'
    if tenant_name.upper() == 'VDJSERVER-ORG':
        return 'https://vdj-agave-api.tacc.utexas.edu'
    return 'http://172.17.0.1:8000'


def get_service_accounts(tenant_name):
    service_accounts = {"DESIGNSAFE": ["prjadmin", "ds_admin"]}
    return service_accounts.get(tenant_name.upper(), [])