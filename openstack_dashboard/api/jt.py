from dateutil import parser
from django.conf import settings
from horizon import conf
from openstack_dashboard.api import base
from openstack_dashboard.api import swift
import json
import MySQLdb
import requests

def _dbconnect():
    username = getattr(settings, 'RAC_MYSQL_USERNAME')
    password = getattr(settings, 'RAC_MYSQL_PASSWORD')
    host = getattr(settings, 'RAC_MYSQL_HOST')
    return MySQLdb.connect(host=host,user=username,passwd=password,db='rac_information')

def is_leased_flavor(flavor_name):
    leased_flavors = getattr(settings, 'RAC_LEASED_FLAVORS', [])
    return flavor_name in leased_flavors

def get_instance_lease(instance_id, project_id, region):
    try:
        db = _dbconnect()
        c = db.cursor()
        query = "SELECT date_format(expiration_date, '%%M %%d, %%Y %%h:%%i %%p') from instance_leases where instance_id = %s and project_id = %s and region = %s"
        data = (instance_id, project_id, region)
        c.execute(query, data)
        instance_lease = c.fetchone()
        if instance_lease is not None:
            return instance_lease[0]
        return None
    except MySQLdb.Error, e:
        print(str(e))
        return None

def set_instance_lease(instance_id, project_id, region, lease):
    try:
        db = _dbconnect()
        c = db.cursor()
        query = "INSERT INTO instance_leases (instance_id, project_id, region, expiration_date) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE expiration_date = %s"
        data = (instance_id, project_id, region, lease, lease)
        c.execute(query, data)
        db.commit()
    except Exception as e:
        print(str(e))

def get_swift_quota(request):
    if not base.is_service_enabled(request, "object-store"):
        return 0

    head = swift.swift_api(request).head_account()
    if 'x-account-meta-quota-bytes' in head:
        return int(head['x-account-meta-quota-bytes']) / 1024 / 1024
    return 1048576

def get_swift_usage(request):
    if not base.is_service_enabled(request, "object-store"):
        return 0

    project_id = request.user.tenant_id
    base_url = 'http://yyc-graphite.cloud.cybera.ca/render?from=-7d&width=800&format=json&target='
    query_results = {}
    quota_query = "aliasByNode(smartSummarize(sumSeries(swift.*.project.%s.account_size), '1h', 'sum'), 4)" % project_id

    usage_mb = 0
    try:
        r = requests.get("%s%s" % (base_url, quota_query), timeout=7)
        result = json.loads(r.content)
        if len(result) >= 1 and 'datapoints' in result[0]:
            usage = int(result[0]['datapoints'][-3][0])
            if usage > 0:
                usage_mb = usage / 1024 / 1024
    except:
        pass
    finally:
        return usage_mb
