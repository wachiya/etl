from builtins import range
from datetime import timedelta
from datetime import datetime
from pytz import timezone

import airflow
from airflow.models import DAG
from airflow.operators.mysql_operator import MySqlOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.contrib.operators.ssh_operator import SSHOperator
from airflow.operators.dagrun_operator import TriggerDagRunOperator
from airflow.hooks.mysql_hook import MySqlHook
from airflow.operators.python_operator import BranchPythonOperator
### CONSTANTS: DO NOT EDIT ###
## TRIGGER RULES
ONE_SUCCESS = 'one_success'

## MYSQL CONNECTION
MYSQL_CONN_ID = 'amrs_slave_conn'

## DAG ID
DAG_ID = 'etl_jobs_realtime'
SLEEP_DAG_ID = 'check_dag'
### END TRIGGER RULES ###

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': ['fali@ampath.or.ke'],
    'email_on_failure': True,
    'email_on_retry': True,
    'start_date': '2019-05-20',
    'retries': 0,
    'retry_delay': timedelta(minutes=30),
}



dag = DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    schedule_interval=None,
    dagrun_timeout=timedelta(minutes=60),
    catchup=False,
    template_searchpath=[
    '/usr/local/airflow/etl-scripts/flat_tables', 
    '/usr/local/airflow/etl-scripts/calculated_tables', 
    '/usr/local/airflow/etl-scripts/database_updates'
    ]
)


class CustomMySqlOperator(MySqlOperator):
    def execute(self, context):
        self.log.info('Executing: %s', self.sql)
        hook = MySqlHook(mysql_conn_id=self.mysql_conn_id,
                         schema=self.database)
        return hook.get_records(self.sql, parameters=self.parameters)


update_flat_obs = MySqlOperator(
    task_id='update_flat_obs',
    sql='flat_obs_v1.3.sql',
    mysql_conn_id=MYSQL_CONN_ID,
    database='etl',
    dag=dag
)



update_flat_orders = MySqlOperator(
    task_id='update_flat_orders',
    sql='flat_orders_v1.1.sql',
    mysql_conn_id=MYSQL_CONN_ID,
    database='etl',
    dag=dag
)

update_flat_lab_obs = MySqlOperator(
    task_id='update_flat_lab_obs',
    sql='flat_lab_obs_v1.8.sql',
    mysql_conn_id=MYSQL_CONN_ID,
    database='etl',
    dag=dag
)


wait = BashOperator(
    task_id='wait',
    bash_command="echo 'Finished all base table jobs' && sleep 5s",
    dag=dag,
)

update_hiv_summary = MySqlOperator(
    task_id='update_hiv_summary',
    sql='call generate_hiv_summary_v15_11("sync",1,15000,20);',
    mysql_conn_id=MYSQL_CONN_ID,
    database='etl',
    dag=dag
)


#update_hiv_summary = SSHOperator(
#    task_id="update_hiv_summary",
#    command="cd /opt/etl-sync-scripts && node hiv-summary-job.js",
#    ssh_conn_id='.115',
#    dag=dag)


update_vitals = MySqlOperator(
    task_id='update_vitals',
    sql='vitals_v2.1.sql',
    mysql_conn_id=MYSQL_CONN_ID,
    database='etl',
    dag=dag
)

update_flat_labs_and_imaging = MySqlOperator(
    task_id='update_flat_labs_and_imaging',
    sql='sync_flat_labs_and_imaging.sql',
    mysql_conn_id=MYSQL_CONN_ID,
    database='etl',
    dag=dag
)

#update_pep_summary = CustomMySqlOperator(
#    task_id='update_pep_summary',
#    sql='pep_summary_v1.0.sql',
#    mysql_conn_id=MYSQL_CONN_ID,
#    database='etl',
#    dag=dag
#)

#update_appointments = SSHOperator(
#    task_id="update_appointments",
#    command="cd /opt/etl-sync-scripts && node appointments-job.js",
#    ssh_conn_id='.115',
#    dag=dag)


update_appointments = MySqlOperator(
    task_id='update_appointments',
    sql='call generate_flat_appointment_v1_1("sync",1,15000,20);',
    mysql_conn_id=MYSQL_CONN_ID,
    database='etl',
    dag=dag
)

update_onc_tables =  MySqlOperator(
    task_id='update_onc_tables',
    sql='sync_onc_tables.sql',
    mysql_conn_id=MYSQL_CONN_ID,
    database='etl',
    dag=dag
)


update_cdm_summary = MySqlOperator(
    task_id='update_cdm_summary',
    sql='sync_cdm_summary_and_monthly_set.sql',
    mysql_conn_id=MYSQL_CONN_ID,
    database='etl',
    dag=dag
)

update_defaulters =  MySqlOperator(
    task_id='update_defaulters',
    sql='call generate_defaulters();',
    mysql_conn_id=MYSQL_CONN_ID,
    database='etl',
    dag=dag
)



finito = DummyOperator(
    task_id='finito',
    dag=dag
)


def decide_which_path():
    now = datetime.now(timezone('Africa/Nairobi'))
    print('Current Hour in Africa/Nairobi')
    print(now.hour);
    if now.hour >= 5 and now.hour <= 21:
        return "rerun_trigger"
    else:
        return "sleep_trigger"

branch = BranchPythonOperator(
    task_id='branch',
    python_callable=decide_which_path,
    trigger_rule="all_done",
    dag=dag)



rerun_trigger = TriggerDagRunOperator(
    task_id='rerun_trigger',
    trigger_dag_id=DAG_ID,
    dag=dag
)


sleep_trigger = TriggerDagRunOperator(
    task_id='sleep_trigger',
    trigger_dag_id=SLEEP_DAG_ID,
    dag=dag
)

update_flat_obs >> wait
update_flat_orders >> wait
update_flat_lab_obs >> wait

wait >> update_hiv_summary
wait >> update_flat_labs_and_imaging
#wait >> update_pep_summary
wait >> update_vitals


update_hiv_summary >> update_defaulters >> update_appointments >> update_onc_tables >> update_cdm_summary >>  finito
update_flat_labs_and_imaging >> finito
update_vitals >> finito


finito >> branch
branch >> rerun_trigger
branch >> sleep_trigger

if __name__ == "__main__":
    dag.cli()
