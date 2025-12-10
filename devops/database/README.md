Devop files for `geoapi-database`.

Use Makefile:

```
make stop
make start
```

## IMPORTANT SETUP NOTES

- When initially deploying the postgis container on a new host,
- In the /geoapi/devops/database/docker-compose-database.yml file,
- Before running the intital `make start` command,
- Comment out line 7: `#- ./postgresql.conf:/var/lib/postgresql/data/postgresql.conf:ro`,
- IF YOU DO NOT you will encounter read and permission errors on the `/database` folder on the host system.
- After the initial container deployment is running and the db is initialized,
- Stop the container `make stop`,
- Edit the config to re-enable line 7 in the `postgresql.conf file`: `#- ./postgresql.conf:/var/lib/postgresql/data/postgresql.conf:ro`,
- Start the container again with `make start`,
- It should now successfully run using the custom `postgresql.conf` file.

To verify settings in the running container:
- `ssh geoapi-database.*`                           # ssh into host
- `sudo -i`                                         # become root
- `docker exec -it geoapi_postgres bash`            # exec into container
- `su - postgres`                                   # become postgres
- `psql -U geoapi -c 'SHOW config_file'`            # get config file location
- `exit`                                            # exit postgres
- `cat /var/lib/postgresql/data/postgresql.conf`    # display the config file
- `exit`                                            # exit container
- `exit`                                            # exit root
- `exit`                                            # exit host

