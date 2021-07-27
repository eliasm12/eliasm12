import logging
import os
import re
from slack_bolt import App
import mysql.connector
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import json

logging.basicConfig(level=logging.DEBUG)

# Initializes your app with your bot token and signing secret
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)
slack_token = os.environ["SLACK_BOT_TOKEN"]
client = WebClient(token=slack_token)

#database connection
mydb = mysql.connector.connect(
  host=os.environ.get("DBHOST"),
  user=os.environ.get("DBUSER"),
  password=os.environ.get("DBPASSWORD"),
  database=os.environ.get("DBDATABASE"),
  raise_on_warnings= True
)

#middleware
@app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    logger.debug(body)
    return next()

def get_projectslackchannelsid_from_channelid(channel_id):
    logging.info('+++++++++++++++++++++++++++++++++-------------channel_id')
    logging.info(channel_id)
    mycursor = mydb.cursor(buffered=True)
    sql = """SELECT project_slack_channels_id FROM project_slack_channels where channel_id = %s"""
    mycursor.execute(sql , (channel_id,))
    myresult = mycursor.fetchone()
    logging.info(myresult[0])
    mycursor.close()
    mydb.close()
    return myresult[0]

def get_user_id_from_username(username):
    mycursor = mydb.cursor()
    sql = """SELECT slack_user_id FROM users where username = %s"""
    mycursor.execute(sql , (username,))
    myresult = mycursor.fetchone()
    mycursor.close()
    mydb.close()
    return myresult[0]

def get_username_from_user_id(user_id):
    mycursor = mydb.cursor()
    sql = """SELECT username FROM users where slack_user_id = %s"""
    mycursor.execute(sql , (user_id,))
    myresult = mycursor.fetchone()
    mycursor.close()
    mydb.close()
    return myresult[0]

def insert_create_task(project_slack_channels_id,user_id):
    mycursor = mydb.cursor()
    sql = """INSERT INTO tasks (project_slack_channels_id,slack_user_id) VALUES (%s,%s)"""
    mycursor.execute(sql , (project_slack_channels_id,user_id,))
    mydb.commit()
    #TODO try catch
    mycursor.close()
    mydb.close()
    return mycursor.lastrowid

def insert_task_detail(task_id,name,value):
    mycursor = mydb.cursor()
    sql = """INSERT INTO task_details (task_id,name,value) VALUES (%s,%s,%s)"""
    mycursor.execute(sql , (task_id,name,value,))
    mydb.commit()
    mycursor.close()
    mydb.close()
    #TODO try catch check if inserted
    return 1    

def insert_task_status(task_id,task_status,user_id):
    mycursor = mydb.cursor()
    sql = """INSERT INTO track_task_status (task_id,task_status,slack_user_id) VALUES (%s,%s,%s)"""
    mycursor.execute(sql , (task_id,task_status,user_id,))
    mydb.commit()
    mycursor.close()
    mydb.close()
    #TODO try catch check inf inseretd
    return 1    

def create_task(task_name , severity , user_id,username, channel_id,task_description):
    project_slack_channels_id = get_projectslackchannelsid_from_channelid(channel_id)
#check if project_id is present 
    if project_slack_channels_id:
        #TODO check for duplicate task name
        task_id = insert_create_task(project_slack_channels_id,user_id)
        if task_id:
            set_task_status = insert_task_status(task_id,'open',user_id)
            res_task_name = insert_task_detail(task_id,"task_name",task_name)
            res_severity = insert_task_detail(task_id,"severity",severity)
            res_desc = insert_task_detail(task_id,"task_description",task_description)
            if res_task_name and res_severity and res_desc and set_task_status:
                return f"Created Ticket: {task_name} TicketID: {task_id} By: {username} with Severity Level: {severity}"
            else:
                return "Error creating Ticket details"
        else:
            return "Error Creating Ticket"
    else:
        return "Error Project Not Found"

def chat_send_message(channel_id,result):
    try:
        response = client.chat_postMessage(
            channel=channel_id,
            text=result
            )
    except SlackApiError as e:
        # You will get a SlackApiError if "ok" is False
        assert e.response["error"]    # str like 'invalid_auth', 'channel_not_found'

def chat_send_message_epthernal(channel_id,result,user_id):
    try:
        response = client.chat_postEphemeral(
            channel=channel_id,
            text=result,
            user=user_id
            )
    except SlackApiError as e:
        # You will get a SlackApiError if "ok" is False
        assert e.response["error"]    # str like 'invalid_auth', 'channel_not_found'


def get_task_attribute(task_id,name):
    mycursor = mydb.cursor()
    sql = """SELECT value FROM task_details where task_id = %s AND name = %s"""
    mycursor.execute(sql , (task_id,name,))
    myresult = mycursor.fetchone()
    mycursor.close()
    mydb.close()
    return myresult[0]            

def list_channel_taks_table(myresult,task_status):
    result = f"Tasks with Status : {task_status} \n"   
    result += "ID         Severity        Name\n"
    for x in myresult:
        if get_task_latest_status(x[0]) == task_status:
            taskname = get_task_attribute(x[0],"task_name")
            severity = get_task_attribute(x[0],"severity")
            result += f"{x[0]}      {severity}      {taskname}\n"
    return result


def get_channel_tasks(channel_id):
    mycursor = mydb.cursor(buffered=True)
    sql = """
        SELECT DISTINCT tasks.task_id 
        FROM (tasks
        INNER JOIN project_slack_channels ON tasks.project_slack_channels_id = project_slack_channels.project_slack_channels_id)
        WHERE project_slack_channels.channel_id = %s 
        """
    mycursor.execute(sql , (channel_id,))
    myresult = mycursor.fetchall()
    mycursor.close()
    mydb.close()
    return myresult

def get_task_latest_status(task_id):
    mycursor = mydb.cursor(buffered=True)
    sql = """
    SELECT task_id,task_status
    FROM track_task_status
    WHERE task_id = %s
    ORDER BY track_task_status_id DESC
          """
    mycursor.execute(sql , (task_id,))
    myresult = mycursor.fetchone()
    mycursor.close()
    mydb.close()
    return myresult[1]


def get_track_latest_status(task_id,user_id):
    mycursor = mydb.cursor(buffered=True)
    sql = """
    SELECT cmd
    FROM task_track
    WHERE task_id = %s AND user_id = %s
    ORDER BY task_track DESC
          """
    mycursor.execute(sql , (task_id,user_id,))
    myresult = mycursor.fetchone()
    mycursor.close()
    mydb.close()
    try:
        logging.info(myresult[0])
        return myresult[0]
    except:
        return 0

def insert_track_cmd(task_id,cmd,user_id):
    mycursor = mydb.cursor()
    sql = """INSERT INTO task_track (task_id,cmd,user_id) VALUES (%s,%s,%s)"""
    mycursor.execute(sql , (task_id,cmd,user_id,))
    mydb.commit()
    mycursor.close()
    mydb.close()
    #TODO check insert if succesful
    return mycursor.lastrowid

def assign_user_task(task_id,user_id,assign_user):
    mycursor = mydb.cursor()
    sql = """INSERT INTO task_users (task_id,assigner,slack_user_id) VALUES (%s,%s,%s)"""
    mycursor.execute(sql , (task_id,user_id,assign_user,))
    mydb.commit()
    mycursor.close()
    mydb.close()
    #TODO check insert if succesful
    return mycursor.lastrowid

def track_task(task_id,channel_id,cmd,user_id):
    if get_task_latest_status(task_id) == 'open':
        #TODO check if there was a stop or no previous request to track task b4 start
        logging.info(get_track_latest_status(task_id,user_id))
        if get_track_latest_status(task_id,user_id) != cmd:
            if insert_track_cmd(task_id,cmd,user_id):
                return 1
            else:
                return 0
        else:
            return 0
    else:
        return 0


def get_started_tasks_task_id(user_id):
    mycursor = mydb.cursor(buffered=True)
    sql = """
    SELECT task_id
    FROM task_track
    WHERE user_id = %s
    ORDER BY task_track DESC
          """
    mycursor.execute(sql , (user_id,))
    mycursor.close()
    mydb.close()
    myresult = mycursor.fetchall()
    return myresult

@app.command("/track")
def handle_track_command(ack, body):
    user_id = body["user_id"]
    channel_name = body["channel_name"]
    channel_id = body["channel_id"]
    command = body["text"]
    command_chunks = command.split()
    track_com = command_chunks[1]
    task_id_str = command_chunks[0]
    if task_id_str.isnumeric():
        task_id=int(task_id_str)
        if track_com == "start" or track_com == "stop": 
                if track_task(task_id,channel_id,track_com,user_id):
                    ack(f"Tracking {track_com} for {channel_name} and task ID: {task_id}")
                else:
                    ack("Error! please check if task is open and if its already being tracked")
        else:
            ack(f"🤬 incorrect command usage , please use either start or stop to track task time")
    else:
            ack(f"🤬 incorrect command usage , provide task ID , use /list to list tasks and tasks ID")


@app.command("/list")
def handle_track_command(ack, body, logger):
    ack()
    channel_id = body["channel_id"]
    command = body["text"]
    user_id = body["user_id"]
    command_chunks = command.split()
    task_status = command_chunks[0]
    try:
        if command_chunks[1]:
            task_user = command_chunks[1]
    except IndexError:
        task_user = user_id
    result = "incorrect command usage, allowed values : open or closed \n To Display tasks from all users in this channel append : -all"
    if task_status == "open" or task_status == "closed":
        if task_user == '-all':
                result = list_channel_taks_table(get_channel_tasks(channel_id),task_status)
        elif task_user == user_id:
                result = "currently not supported yet , please use -all"
    chat_send_message_epthernal(channel_id,result,user_id)
    logger.info(result)



@app.command("/current")
def handle_time_command(ack, body, logger):
    ack()
    channel_id = body["channel_id"]
    command = body["text"]
    user_id = body["user_id"]
    command_chunks = command.split()
    result = "incorrect command usage, \n To Display open tasks tracks for this channel use : `/current`"
    result= get_started_tasks(user_id)
    chat_send_message_epthernal(channel_id,result,user_id)
    logger.info(result)



@app.command("/create")
def handle_create_command(body, ack, respond, client, logger):
    ack()
    channel_id = body["channel_id"]
    respond()
    res = client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "view-id",
            "title": {
                "type": "plain_text",
                "text": "Create a New Task",
            },
            "submit": {
                "type": "plain_text",
                "text": "Submit",
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel",
            },
            "private_metadata": channel_id,
            "blocks": [
                {
                    "type": "input",
                    "block_id" : "task_name",
                    "element": {
                        "type": "plain_text_input"
                                },
                    "label": {
                        "type": "plain_text",
                        "text": "Task Name",
                    },
                },
                {
                    "type": "input",
                    "block_id" : "task_description",
                    "element": {
                        "type": "plain_text_input",
                        "multiline" : True
                                },
                    "label": {
                        "type": "plain_text",
                        "text": "Description",
                    },
                },
		{
			"type": "section",
                        "block_id" : "severity",
			"text": {
				"type": "mrkdwn",
				"text": "Select Severity Level"
			},
			"accessory": {
				"type": "static_select",
				"placeholder": {
					"type": "plain_text",
					"text": "Severity Level",
				},
				"options": [
					{
						"text": {
							"type": "plain_text",
							"text": "Urgent",
						},
						"value": "urgent"
					},
					{
						"text": {
							"type": "plain_text",
							"text": "High",
						},
						"value": "high"
					},
					{
						"text": {
							"type": "plain_text",
							"text": "Normal",
						},
						"value": "normal"
					}
				],
				"action_id": "static_select-action"
			}
		},


                ],
        },
    )




@app.command("/assign")
def handle_assign_command(ack, body, logger):
    ack()
    result="test"
    channel_id = body["channel_id"]
    command = body["text"]
    user_id = body["user_id"]
    cusername = body["user_name"]
    command_chunks = command.split()
    task_id_str = command_chunks[0]
    if task_id_str.isnumeric():
        task_id=int(task_id_str)
        if get_task_latest_status(task_id) == 'open':
            try:
                if command_chunks[1]:
                    username = command_chunks[1].replace("@","")
                    assign_user_id = get_user_id_from_username(username)
                    #TODO check if user allowed to receive tickets also make sure that this ticket was not previously assigned to him
                    if assign_user_task(task_id,user_id,assign_user_id):
                        task_name = get_task_attribute(task_id,"task_name");
                        result = f"Assigned Task {task_id} : {task_name} to {command_chunks[1]} By {cusername}"
            except IndexError:
                result = "Error use ' /list open -all ' to check open tickets and assign them /n command usage: /assign task_id @user"
        else:
            result = "Double check the Task ID and if it was still open \n you can use : ' /list open -all '"
    chat_send_message(channel_id,result)
    logger.info(result)


@app.command("/resolve")
def handle_close_command(ack, body, logger):
    ack()
    result="test"
    channel_id = body["channel_id"]
    command = body["text"]
    user_id = body["user_id"]
    cusername = body["user_name"]
    command_chunks = command.split()
    task_id_str = command_chunks[0]
    error = 1 
    if task_id_str.isnumeric():
        task_id=int(task_id_str)
        if get_task_latest_status(task_id) == 'open':
            try:
                if command_chunks[1]:
                    comment = body["text"]
                    if insert_task_status(task_id,'closed',user_id):
                        task_name = get_task_attribute(task_id,"task_name");
                        result = f"Task closed {task_id} : {task_name} \n Reason: {comment} By {cusername}"
                        error = 0
            except IndexError:
                result = "Error Please Add Comment \n command usage: /resolve task_id comment)"
        else:
            result = "Error Task ID dont seem to be still open or valid \n you can use : ' /list open -all ' to check opened ones"
    else:
        result = "Error check command usage \n command usage: /resolve task_id comment "
    if error == 0:
        chat_send_message(channel_id,result)
    else:
        chat_send_message_epthernal(channel_id,result)
    logger.info(result)


@app.action("static_select-action")
def handle_severity_option(ack, body, logger):
    ack()

@app.view("view-id")
def view_submission(ack, body, logger):
    ack()
    user_id = body["user"]["id"]
    username= body["user"]["username"]
    channel_id = body["view"]["private_metadata"]
    logger.info(channel_id)
    arrval = body["view"]["state"]["values"]
    task_name_key = next(iter(arrval["task_name"]))
    task_name = arrval["task_name"][task_name_key]["value"]
    task_description_key = next(iter(arrval["task_description"]))
    task_description = arrval["task_description"][task_description_key]["value"]
    severity = arrval["severity"]["static_select-action"]["selected_option"]["value"]
    ack()
    logger.info("b4create***************************")
    result = create_task(task_name , severity , user_id,username, channel_id,task_description)
    chat_send_message(channel_id,result)
    logger.info(result)


@app.error
def global_error_handler(error, body, logger):
    logger.exception(error)
    logger.info(body)


# Start your app
if __name__ == "__main__":
    app.start(3000)

