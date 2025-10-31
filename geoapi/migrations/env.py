from logging.config import fileConfig
from geoapi.log import logger
from alembic import context
from geoapi.models import *  # noqa: F401, F403 important to include all models for autogenerate support; do not delete
from geoapi.db import Base


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def include_object(object, name, type_, reflected, compare_to):
    """Filter objects for Alembic migrations, specifically handling PostGIS tables/schemas.

    PostGIS manages its own schema updates through the extension system. This prevents our
    application migrations from conflicting with PostGIS's internal version management and
    schema updates. When PostGIS is upgraded, it will handle its own schema migrations.

    """

    # Get schema info
    schema = getattr(object, "schema", None)
    if schema is None and type_ == "index" and hasattr(object, "table"):
        schema = object.table.schema

    # Tiger/PostGIS related tables and sequences to exclude
    excluded_tables = [
        "layer",
        "topology",
        "geocode_settings_default",
        "street_type_lookup",
        "county",
        "zip_lookup_base",
        "bg",
        "zip_lookup",
        "direction_lookup",
        "state_lookup",
        "featnames",
        "tract",
        "addrfeat",
        "loader_platform",
        "loader_lookuptables",
        "zip_state_loc",
        "tabblock",
        "cousub",
        "addr",
        "county_lookup",
        "loader_variables",
        "place_lookup",
        "zip_lookup_all",
        "geocode_settings",
        "place",
        "secondary_unit_lookup",
        "faces",
        "pagc_lex",
        "countysub_lookup",
        "tabblock20",
        "pagc_rules",
        "edges",
        "state",
        "zcta5",
        "zip_state",
        "pagc_gaz",
    ]

    excluded_sequences = [
        "county_gid_seq",
        "state_gid_seq",
        "addr_gid_seq",
        "edges_gid_seq",
        "pagc_lex_id_seq",
        "cousub_gid_seq",
        "addrfeat_gid_seq",
        "place_gid_seq",
        "bg_gid_seq",
        "faces_gid_seq",
        "pagc_rules_id_seq",
        "tabblock_gid_seq",
        "tract_gid_seq",
        "featnames_gid_seq",
        "zcta5_gid_seq",
        "pagc_gaz_id_seq",
    ]

    # Check schemas first
    if schema in ["tiger", "topology"]:
        logger.info(f"Excluding {type_} {name} due to schema {schema}")
        return False

    # Check type-specific exclusions
    if type_ == "table":
        if name == "spatial_ref_sys" or name.lower() in excluded_tables:
            logger.info(f"Excluding table {name}")
            return False

    elif type_ == "index" and hasattr(object, "table"):
        table_name = object.table.name.lower()
        if table_name in excluded_tables:
            logger.info(f"Excluding index {name} for excluded table {table_name}")
            return False

    elif type_ == "sequence":
        if name.lower() in excluded_sequences:
            logger.info(f"Excluding sequence {name}")
            return False

    logger.info(f"Including {type_} {name}")
    return True


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    from geoapi.db import migrate_engine

    # connectable = engine_from_config(
    #     config.get_section(config.config_ini_section),
    #     prefix="sqlalchemy.",
    #     poolclass=pool.NullPool,
    # )

    with migrate_engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
