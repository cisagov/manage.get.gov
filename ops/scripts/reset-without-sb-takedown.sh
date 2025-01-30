#unbind the service
cf unbind-service getgov-env getgov-env-database
#delete the service key
cf delete-service-key getgov-rh-database SERVICE_CONNECT 
#delete the service
cf delete-service getgov-env-database
#create it again
cf create-service aws-rds micro-psql getgov-env-database
# wait for it be created (up to 5 mins)
# this checks the creation cf service getgov-env-database
# the below command with check “status” line using cf service command mentioned above. if it says “create in progress” it will keep waiting otherwise the next steps fail

until cf service getgov-$1-database | grep -q 'The service instance status is succeeded'
do
  echo "Database not up yet, waiting..."
  sleep 30
done

#rebind the service
cf bind-service getgov-env getgov-env-database
#restage the app or it will not connect to the database right for the next commands
cf restage getgov-env
#wait for the above command to finish
#if it is taking way to long and the annoying “instance starting” line that keeps repeating, then run following two commands in a separate window. This will interrupt the death loop where it keeps hitting an error with it failing health checks
#create the cache table and run migrations
cf run-task getgov-env --command 'python manage.py createcachetable' --name createcachetable
cf run-task getgov-env --command 'python manage.py migrate' --name migrate

#check that your cloud.gov logs show this is done before you run the following command (or be like me and you have to run the command again because you were impatient. Running this before the migrate finishes will cause an error)
#load fixtures
cf run-task getgov-env --command 'python manage.py load' --name loaddata