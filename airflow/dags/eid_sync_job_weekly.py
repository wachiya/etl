from builtins import range
from datetime import timedelta
from datetime import datetime
import logging
import math
from pytz import timezone

from airflow.contrib.operators.ssh_operator import SSHOperator
import airflow
from airflow.models import DAG

nbo_timezone = timezone("Africa/Nairobi")
start_date = nbo_timezone.localize(datetime.strptime('2019-06-25 20:00', '%Y-%m-%d %H:%M'))

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': ['fali@ampath.or.ke'],
    'email_on_failure': True,
    'email_on_retry': True,
    'email_on_success': True,
    'start_date': start_date,
    'retries': 5,
    'retry_delay': timedelta(minutes=15),
}

dag = DAG(
    dag_id='sync_eid_labs_weekly_sat_10pm',
    default_args=default_args,
    schedule_interval= '0 22 * * 6',
    dagrun_timeout=timedelta(minutes=60)
)

sync_eid_sync_alupe = SSHOperator(
    task_id="sync_eid_sync_alupe",
    command="docker run  -v /opt/eid/conf:/opt/etl/conf --name ubuntu_bash --rm -i 10.50.80.56:5005/eid-services:latest babel-node /opt/etl/worker/schedule-eid-sync.script.js --lab=alupe --weekly=true",
    ssh_conn_id='.56',
    dag=dag)

sync_eid_sync_ampath = SSHOperator(
    task_id="sync_eid_sync_ampath",
    command="docker run  -v /opt/eid/conf:/opt/etl/conf --name ubuntu_bash --rm -i 10.50.80.56:5005/eid-services:latest babel-node /opt/etl/worker/schedule-eid-sync.script.js --lab=ampath --weekly=true",
    ssh_conn_id='.56',
    dag=dag)

sync_eid_sync_alupe >> sync_eid_sync_ampath
