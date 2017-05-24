from dateutil import parser
from django.conf import settings
from horizon import conf
from openstack_dashboard.api import base
from openstack_dashboard.api import swift
import json
import MySQLdb
import requests

limit_names = {
    'cores': 'maxTotalCores',
    'instances': 'maxTotalInstances',
    'ram': 'maxTotalRAMSize',
    'server_groups': 'maxServerGroups',

    'floatingip': 'maxTotalFloatingIps',
    'security_group': 'maxSecurityGroups',
    'security_group_rule': 'maxSecurityGroupRules',

    'gigabytes': 'maxTotalVolumeGigabytes',
    'snapshots': 'totalSnapshotsUsed',
    'volumes': 'maxTotalVolumes',

    'object_mb': 'object_storage_quota'
}

limit_defaults = {
    'cores': 8,
    'instances': 8,
    'ram': 8192,
    'floatingip': 1,
    'security_group': 10,
    'volumes': 10,
    'gigabytes': 500,
    'object_mb': 1048576,
}

usage_names = {
    'cores': 'totalCoresUsed',
    'instances': 'totalInstancesUsed',
    'ram': 'totalRAMUsed',
    'server_groups': 'totalServerGroupsUsed',

    'floatingip': 'totalFloatingIpsUsed',
    'security_group': 'totalSecurityGroupsUsed',
    'security_group_rule': 'totalSecurityGroupUsed',

    'gigabytes': 'totalGigabytesUsed',
    'volumes': 'totalVolumesUsed',
    'snapshots': 'totalSnapshotsUsed',

    'object_mb': 'object_storage_used'
}

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

def get_master_quotas(request):
    quotas = {}
    try:
        db = _dbconnect()
        c = db.cursor()
        query = "SELECT resource, quota from quotas where project_id = %s"
        data = (request.user.tenant_id)
        c.execute(query, data)
        rows = c.fetchall()
        for row in rows:
            quotas[row[0]] = row[1]
        return quotas
    except MySQLdb.Error, e:
        print(str(e))
        return None

def get_rac_usage(request):
    usage = {}
    try:
        db = _dbconnect()
        c = db.cursor()
        query = "select resource, sum(in_use) as in_use from resource_usage where project_id = %s group by resource"
        data = (request.user.tenant_id)
        c.execute(query, data)
        rows = c.fetchall()
        for row in rows:
            usage[row[0]] = row[1]
        return usage
    except MySQLdb.Error, e:
        print(str(e))
        return None

def generate_limits(request):
    limits = {}
    for default, limit in limit_defaults.iteritems():
        limits[limit_names[default]] = limit
    for resource, quota in get_master_quotas(request).iteritems():
        if resource in limit_names:
            limits[limit_names[resource]] = int(quota)
    for resource, in_use in get_rac_usage(request).iteritems():
        if resource in usage_names:
            limits[usage_names[resource]] = int(in_use)
    limits['object_storage_used'] = get_swift_usage(request)
    return limits

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
