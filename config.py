SHINGLE_N = 5
MINHASH_RANDOM_SEED = 42
DEFAULT_HASH_PARAMETER = 128
MINHASH_PRIME = 2_147_483_647
BATCH_TOP_N = 50

DB_CONFIG_BY_ENV = {
    "dev": {
        "MYSQL_HOST": "10.1.92.25",
        "MYSQL_PORT": 3306,
        "MYSQL_USER": "product",
        "MYSQL_PASSWORD": "product321",
        "MYSQL_DB": "platform",
        "MYSQL_CHARSET": "utf8mb4",
    },
    "uat": {
        "MYSQL_HOST": "47.101.222.159",
        "MYSQL_PORT": 3310,
        "MYSQL_USER": "uat_ai",
        "MYSQL_PASSWORD": "ACLSnkg4HNyt",
        "MYSQL_DB": "platform_uat",
        "MYSQL_CHARSET": "utf8mb4",
    },
    "prod": {
        "MYSQL_HOST": "jhpy.rwlb.rds.aliyuncs.com",
        "MYSQL_PORT": 3306,
        "MYSQL_USER": "reader",
        "MYSQL_PASSWORD": "nP42UJkmp5oYWRhN",
        "MYSQL_DB": "super_campus",
        "MYSQL_CHARSET": "utf8mb4",
    },
}
