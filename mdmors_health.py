import cx_Oracle
import pandas as pd
import subprocess
import requests
import csv
import time
from io import BufferedReader
#import rds_db_idlib3
import os
import datetime
from datetime import datetime
import platform


rds_db_schema_list = []
rds_db_rec_count_list = []
rds_db_invalid_schema_list = []
rds_db_total_invalid_schema_list  = []
# Oracle client library configuration (if needed)
# cx_Oracle.init_oracle_client(lib_dir=r"path_to_your_oracle_instant_client")
send_email_flag='N'


def unicode_csv_reader(utf8_data, dialect=csv.excel, **kwargs):
    csv_reader = csv.reader(utf8_data, dialect=dialect, **kwargs)
    for row in csv_reader:
        yield [unicode(cell, 'utf-8') for cell in row]

def send_email(to='', subject='', body=''):
    if not subject:
        raise NoSubjectError
    if not to:
        raise NoRecipientError
    #
    if not body:
        cmd = """mailx -s "{s}" < /dev/null "{to}" 2>/dev/null""".format(s=subject, to=to)
    else:
        cmd = """echo "{b}" | mailx -r dlops@.com -s "{s}" "{to}" 2>/dev/null""".format(b=body, s=subject, to=to )
        
        os.system(cmd)




def fetch_data_to_csv_json(rds_host, db_name, db_user, db_password, port, sql_query, csv_file_path,json_file_path):
    """
    Connect to an Oracle database, execute a SQL query, fetch the data, and save it to a CSV file.

    :param rds_host: Hostname of the RDS instance
    :param db_name: Database name or service name
    :param db_user: Username for the database
    :param db_password: Password for the database
    :param port: Port number for the database connection
    :param sql_query: SQL query to execute
    :param csv_file_path: File path to save the CSV file
    """
    # DSN (Data Source Name) configuration
    dsn_tns = cx_Oracle.makedsn(rds_host, port, service_name=db_name)

    # Establish a connection to the database
    try:
        conn = cx_Oracle.connect(user=db_user, password=db_password, dsn=dsn_tns)
        print("Connected to the database successfully.")

        # Execute the SQL query and fetch the data
        df = pd.read_sql(sql_query, conn)
        print("Query executed and data fetched successfully.")

        # Save the data to a CSV file
        df.to_csv(csv_file_path, index=False,header=None)
        print("Data saved to CSV file at {} successfully.").format(csv_file_path)

        # Save the data to a JSON file
        df.to_json(json_file_path, orient='records', lines=True)
        print("Data saved to JSON file at {} successfully.").format(json_file_path)

    except cx_Oracle.DatabaseError as e:
        error, = e.args
        print("An error occurred: {} - {}").format(error.code,error.message)

    finally:
        # Close the database connection
        if 'conn' in locals() and conn is not None:
            conn.close()
            print("Database connection closed.")

# Example usage:
# Define your database parameters and SQL query
rds_host = "**"
db_name = "emdm"
db_user = "**"
db_password = "**"
port = 1771  # Default port for Oracle
###Replace with your ORS Details
sql_query = "select 'EMDM_ORS' ,count(*)  from emdm_ors.C_REPOS_MET_VALID_RESULT   where trunc(create_date)=trunc(sysdate) and  nerror <>0 union all select 'PRODUCT_ORS'  ,count(*)  from product_ors.C_REPOS_MET_VALID_RESULT  where trunc(create_date)=trunc(sysdate) and  nerror <>0 union all select 'PRODUCT_GXP' ,count(*)  from product_gxp.C_REPOS_MET_VALID_RESULT  where trunc(create_date)=trunc(sysdate) and  nerror <>0"


print("sql_query={}").format(sql_query)
csv_file_path = '/path/mdmors_health_report.csv'
json_file_path ='/path/mdmors_health_report.json'

# Call the function with the specified parameters
fetch_data_to_csv_json(rds_host, db_name, db_user, db_password, port, sql_query, csv_file_path,json_file_path)

########### Read MDM ORS health report /CSV file  #############################

csv_file_path_without_header='/path/mdmors_health_report.csv'


filename = csv_file_path_without_header
reader = unicode_csv_reader(open(filename))
for field1 in reader:
    #print field1, field2, field3
    #print field1
    if (field1):

        rds_db_schema=field1[0]
        rds_db_rec_count=field1[1]
        print('rds_db_schema='+rds_db_schema)
        rds_db_schema_list.append(rds_db_schema)
        rds_db_rec_count_list.append(rds_db_rec_count)

        print('rds_db_schema={} and rds_db_rec_count={}'.format(rds_db_schema,rds_db_rec_count))

        #time.sleep(SLEEP)
        rec_count=int(rds_db_rec_count.strip())
        print('rec_count=={}'.format(rec_count))
        if ( rec_count > 0 ):
            send_email_flag='Y'
            rds_db_invalid_schema_list=[rds_db_schema,rds_db_rec_count]
            rds_db_total_invalid_schema_list.append(rds_db_invalid_schema_list)
        else:
            send_email_flag='N'

####################Email -Notification Message Formation######################
invalid_count=len(rds_db_total_invalid_schema_list)
Message1=''
for i in range(len(rds_db_total_invalid_schema_list)):
    rds_db_schema=rds_db_total_invalid_schema_list[i][0]
    rds_db_rec_count=rds_db_total_invalid_schema_list[i][1]
    if (rds_db_rec_count > 0):
        status='Invalid'
        send_email_flag='Y'
    else:
        status='Valid'
        send_email_flag='N'

    Message1=Message1+"\n MDM ORS: {} is {}. ORS Error Count:{}\n".format( rds_db_schema,status,rds_db_rec_count)
    print('Message1='+Message1)

#################### Send Email -Notification to Team######################

if ( invalid_count <> 0):
    body_Message="Dear Support Team,\n\nPlease take necessary action. \n\n -----------------Prod MDM ORS Validity Alert ---------------------\n" +Message1+"\n----------------------------------------------------------------\n\n"+"\n \n Thanks,\nEMDM OPS Support Team\n \n [ P.S- This is an automated Alert Email.Please do not reply. ]"
    now = datetime.now() # current date and time
    date = now.strftime("%m/%d/%Y, %H:%M:%S")
    #send_email(to="schowd02@amgen.com",subject="EMDM - Prod MDM ORS Validity Alert:"+date,body=body_Message)
    send_email(to="dlops@.com",subject="MDM ORS Validity Alert:"+date,body=body_Message)
    print('Sent Email.invalid_count={}'.format(invalid_count))
else:
    print('Email Not Sent.invalid_count={}'.format(invalid_count))
