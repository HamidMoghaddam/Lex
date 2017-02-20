# Lex
Amazon Lex (https://aws.amazon.com/lex/) provides deep learning models to recognize the intent of the text and enables developers to build sophisticated, natural language, conversational bots (“chatbots”). Although there are several examples of developing a chat bot by Lex (http://docs.aws.amazon.com/lex/latest/dg/lex-dg.pdf), connecting Lex to a database for saving or retrieving data has not provided by those examples. By this project, Lex will be able to get appointment types and available times for an appointment in a specific date from DynamoDB tables and save a requested appointment to the database.

# Database
First a table named "AppointmentType" with a numeric Primary partition key named "ID" should be created. Then a table named "Appointments" with a string Primary partition key named "AppID" should be created. For the second table an index called "Date-Time-index" with Partition Key "Date (String)" and Sort key "Time (String)" is necessary. This index key will be used for getting available times in a date in our lambda function.

# IAM Role
This project needs three IAM roles for connecting Lex to the lambda function, lambda function to DynamoDB and facebook to Lex.
For connecting Lex to lambda function, a IAM role named "lex-exec-role" should be created and [this] (lex-exec-role.txt) used as its Inline Policies. For connecting lambda function to DynamoDB, an IAM role named "LambdatoDynamoDb" should be created and a "AmazonDynamoDBFullAccesswithDataPipeline" policy selected as its Managed Policies. For connecting facebook to Lex, an IAM role named "LexChannelExecutionRole" should be created and [this] (LexChannelExecutionRole.txt) used as its Inline Policies.

# lambda function
First create an blank lambda function and named it "AppointmentScheduler" then choose Python 2.7 for its Runtime and then copy [this] (lambda_function.py) code to the editor (You can upload the code as a zip file too). Then, choose "LambdatoDynamoDb" IAM role as its Existing role and save it. It is worth noting that you can test the lambda function by choosing "Lex- Make appointment" as a Sample event template.

# Lex
First create a ScheduleAppointment Bot in Lex console and choose "lex-exec-role" role as its IAM role. Then, select "Initialization and validation code hook" in options and "AWS Lambda function" in Fulfillment then choose the lambda function ("AppointmentScheduler") for them. Finally, you can build and test your chat bot.

# Publish on Facebook
First publish your chat bot then go to Channels tab of your bot and set a name, "LexChannelExecutionRole" as its IAM role, a Verify token, your Facebook Page access token and App secret key then activate it. For more information please check https://developers.facebook.com and http://docs.aws.amazon.com/lex/latest/dg/lex-dg.pdf.
