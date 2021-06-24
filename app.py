import logging
import os
from slack_bolt import App
import mysql.connector
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

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
    mycursor = mydb.cursor()
    sql = """SELECT project_slack_channels_id FROM project_slack_channels where channel_id = %s"""
    mycursor.execute(sql , (channel_id,))
    myresult = mycursor.fetchone()
    return myresult[0]

def insert_create_task(project_slack_channels_id,user_id):
    mycursor = mydb.cursor()
    sql = """INSERT INTO tasks (project_slack_channels_id,slack_user_id) VALUES (%s,%s)"""
    mycursor.execute(sql , (project_slack_channels_id,user_id,))
    mydb.commit()
    #TODO try catch
    return mycursor.lastrowid

def insert_task_detail(task_id,name,value):
    mycursor = mydb.cursor()
    sql = """INSERT INTO task_details (task_id,name,value) VALUES (%s,%s,%s)"""
    mycursor.execute(sql , (task_id,name,value,))
    mydb.commit()
    #TODO try catch
    return 1    

def create_task(task_name , severity , user_id,username, channel_id,task_description):
    project_slack_channels_id = get_projectslackchannelsid_from_channelid(channel_id)
#check if project_id is present 
    if project_slack_channels_id:
        task_id = insert_create_task(project_slack_channels_id,user_id)
        if task_id:
            res_task_name = insert_task_detail(task_id,"task_name",task_name)
            res_severity = insert_task_detail(task_id,"severity",severity)
            res_desc = insert_task_detail(task_id,"task_description",task_description)
            if res_task_name and res_severity and res_desc:
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
    return myresult[0]            

def get_channel_tasks(channel_id,task_status,task_user):
    mycursor = mydb.cursor()
    if task_user == 'all':
        sql = """SELECT task_id FROM project_slack_channels AS a, tasks AS b where a.project_slack_channels_id = b.project_slack_channels_id AND task_status = %s AND channel_id = %s"""
    else:
        sql = """SELECT task_id FROM project_slack_channels AS a, tasks AS b where a.project_slack_channels_id = b.project_slack_channels_id AND task_status = %s AND channel_id = %s"""
    mycursor.execute(sql , (task_status,channel_id,))
    myresult = mycursor.fetchall()
    result = f"Tasks with Status : {task_status} \n"   
    result += "ID         Severity        Name\n"
    for x in myresult:
        taskname = get_task_attribute(x[0],"task_name")
        severity = get_task_attribute(x[0],"severity")
        result += f"{x[0]}      {severity}      {taskname}\n"
    return result

def insert_track_cmd(task_id,cmd):
    mycursor = mydb.cursor()
    sql = """INSERT INTO task_track (task_id,cmd) VALUES (%s,%s)"""
    mycursor.execute(sql , (task_id,cmd,))
    mydb.commit()
    #TODO check insert if succesful
    return mycursor.lastrowid


def track_task(task_id,channel_id,cmd):
    if check_task_in_channel_status(task_id,channel_id,'open'):
        #TODO check if there was a stop or no previous request to track task b4 start
        if insert_track_cmd(task_id,cmd):
            return 1
        else:
            return 0
    else:
        return 0

def check_task_in_channel_status(task_id,channel_id,task_status):
    mycursor = mydb.cursor()
    sql = """SELECT task_id FROM project_slack_channels AS a, tasks AS b where a.project_slack_channels_id = b.project_slack_channels_id AND task_status = %s AND channel_id = %s AND task_id = %s"""
    mycursor.execute(sql , (task_status,channel_id,task_id))
    myresult = mycursor.fetchone()
    return myresult[0]

@app.command("/track")
def handle_track_command(ack, body):
    channel_name = body["channel_name"]
    channel_id = body["channel_id"]
    command = body["text"]
    command_chunks = command.split()
    track_com = command_chunks[1]
    task_id_str = command_chunks[0]
    if task_id_str.isnumeric():
        task_id=int(task_id_str)
        if track_com == "start" or track_com == "stop": 
                if track_task(task_id,channel_id,track_com):
                    ack(f"Tracking {track_com} for {channel_name} and task ID: {task_id}")
                else:
                    ack("Error!")
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
    
    if task_user == '-all' or task_user == user_id:
        if task_status == "open" or task_status == "closed":
            result = get_channel_tasks(channel_id,task_status,task_user)
    else:
        result = "incorrect command usage, allowed values : open or closed \n To Display tasks from all users in this channel append : -all"
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


@app.action("static_select-action")
def handle_severity_option(ack, body, logger):
    ack()



@app.view("view-id")
def view_submission(ack, body, logger):
    ack()
    user_id = body["user"]["id"]
    username= body["user"]["username"]
    channel_id = body["view"]["private_metadata"]
    arrval = body["view"]["state"]["values"]
    task_name_key = next(iter(arrval["task_name"]))
    task_name = arrval["task_name"][task_name_key]["value"]
    task_description_key = next(iter(arrval["task_description"]))
    task_description = arrval["task_description"][task_description_key]["value"]
    severity = arrval["severity"]["static_select-action"]["selected_option"]["value"]
    ack()
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

