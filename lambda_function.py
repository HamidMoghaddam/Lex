import boto3
import json
import math
import logging
import uuid
from boto3.dynamodb.conditions import Key
from datetime import datetime, time, timedelta
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
dynamodb = boto3.resource('dynamodb')

def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message, response_card):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message,
            'responseCard': response_card
        }
    }
def confirm_intent(session_attributes, intent_name, slots, message, response_card):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': message,
            'responseCard': response_card
        }
    }
def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }
def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response
def try_ex(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.

    Note that this function would have negative impact on performance.
    """

    try:
        return func()
    except KeyError:
        return None
def build_response_card(title, subtitle, options):
    """
    Build a responseCard with a title, subtitle, and an optional set of options which should be displayed as buttons.
    """
    buttons = None
    if options is not None:
        buttons = []
        for i in range(min(5, len(options))):
            buttons.append(options[i])

    return {
        'contentType': 'application/vnd.amazonaws.card.generic',
        'version': 1,
        'genericAttachments': [{
            'title': title,
            'subTitle': subtitle,
            'buttons': buttons
        }]
    }
# Get all type of appointments
def get_appointmentType():
    table = dynamodb.Table('AppointmentType')
    response =table.scan()
    return response
# Get duration time of requested appointment    
def get_duration(appointment_types,name):
    """
    The appointment types table is small so I use python for searching instead 
    of using table query 
    """
    duration=[type['Duration'] for type in appointment_types['Items'] 
        if type['Name'].lower()==name] 
    return duration[0]
    
# Get all reserved time for the requested date    
def get_date_reserved(requested_date):
    table = dynamodb.Table('Appointments')
    response = table.query(IndexName='Date-Time-index',
        KeyConditionExpression=Key('Date').eq(requested_date))
    reserved_time=[[datetime.strptime(requested_date+" "+t['Time'], '%Y-%m-%d %H:%M')
        ,datetime.strptime(requested_date+" "+t['End'], '%Y-%m-%d %H:%M')] for t in response['Items']]
    return reserved_time
def get_availabilities(date):
    availabilities=[]
    reserved_time=get_date_reserved(date)
    open_time,close_time=get_office_hours(date)
    open_time=datetime.strptime(date+" "+open_time, '%Y-%m-%d %H:%M')
    close_time=datetime.strptime(date+" "+close_time, '%Y-%m-%d %H:%M')
    for span in datespan(open_time,close_time,delta=timedelta(minutes=30)):
        counter=0
        for time in reserved_time:
            if time[0]<=span and span <time[1]:
                counter=1
                break
        if counter==0:
            availabilities.append(str(span.time())[0:5])
    return availabilities
def get_office_hours(requested_date):
    date=datetime.strptime(requested_date, '%Y-%m-%d')
    if date.weekday()==5:
        return '10:00','16:00'
    else:
        return '09:00','17:00'

def build_validation_result(is_valid, violated_slot, message_content):
    return {
        'isValid': is_valid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }
    
def validate_book_appointment(appointment_types, requested_appointment, requested_date, requested_time):
    
    
    appointment_list=[type['Name'].lower() for type in appointment_types['Items']]
    if requested_appointment not in appointment_list:
        return build_validation_result(False, 'AppointmentType', 'I did not recognize that, can I book you a '+', '.join(appointment_list) +'?')

    if requested_time:
        open_time,close_time=get_office_hours(requested_date)
        open_hour,open_minute=open_time.split(':')
        close_houre,close_minute=close_time.split(':')
        if len(requested_time) != 5:
            return build_validation_result(False, 'Time', 'I did not recognize that, what time would you like to book your appointment?')

        hour, minute = requested_time.split(':')
        hour = int(hour)
        minute = int(minute)
        if math.isnan(hour) or math.isnan(minute):
            return build_validation_result(False, 'Time', 'I did not recognize that, what time would you like to book your appointment?')

        if hour < int(open_hour) or hour > int(close_houre):
            # Outside of business hours
            return build_validation_result(False, 'Time', 'Our business hours are {} to {} What time works best for you?'.format(
                build_time_output_string(open_time),build_time_output_string(close_time)))
                

        if minute not in [30, 0]:
            # Must be booked on the hour or half hour
            return build_validation_result(False, 'Time', 'We schedule appointments every half hour, what time works best for you?')

    if requested_date:
        date=datetime.strptime(requested_date, '%Y-%m-%d')
        if date < datetime.today():
            return build_validation_result(False, 'Date', 'Your appointment date is in the past!  Can you try a different date?')
        elif date.weekday() == 6:
            return build_validation_result(False, 'Date', 'Our office is not open on the weekends, can you provide a work day?')

    return build_validation_result(True, None, None)

        
def datespan(startDate, endDate, delta=timedelta(minutes=30)):
    currentDate = startDate
    
    while currentDate < endDate:
        yield currentDate
        currentDate += delta
def increment_time_by_thirty_mins(time):
    hour, minute = map(int, time.split(':'))
    return '{}:00'.format(hour + 1) if minute == 30 else '{}:30'.format(hour)

def get_availabilities_for_duration(duration,availabilities):
    duration_availabilities=[]
    delta=timedelta(minutes=int(duration))
    if duration=='30':
        return availabilities
    for i in range(len(availabilities)-2):
        incremented_time=increment_time_by_thirty_mins(availabilities[i])
        # for hour less than 10
        if len(incremented_time)<5:
            incremented_time='0'+incremented_time
        if incremented_time==availabilities[i+1]:
            duration_availabilities.append(availabilities[i])
        
    return duration_availabilities
def build_options(slot, appointment_types,appointment_type, date,booking_map):
    """
    Build a list of potential options for a given slot, to be used in responseCard generation.
    """
    options = []
    day_strings = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    if slot == 'AppointmentType':
        for app in appointment_types['Items']:
            options.append({'text': '{} ({} min)'.format(app['Name'],app['Duration']), 'value':app['Name']})
        
    elif slot == 'Date':
        # Return the next five weekdays.
        
        potential_date = datetime.today()
        while len(options) < 5:
            potential_date = potential_date + timedelta(days=1)
            if potential_date.weekday() < 6:
                options.append({'text': '{}-{} ({})'.format((potential_date.month), potential_date.day, day_strings[potential_date.weekday()]),
                                'value': potential_date.strftime('%A, %B %d, %Y')})
        
    elif slot == 'Time':
        # Return the availabilities on the given date.
        if not appointment_type or not date:
            return None
        availabilities = try_ex(lambda: booking_map[date])
        if not availabilities:
            return None

        duration=get_duration(appointment_types,appointment_type)
        availabilities = get_availabilities_for_duration(duration, availabilities)
        if len(availabilities) == 0:
            return None
        
        for i in range(min(len(availabilities), 5)):
            options.append({'text': build_time_output_string(availabilities[i]), 'value': build_time_output_string(availabilities[i])})

    return options
def build_time_output_string(time):
    hour, minute = time.split(':')  # no conversion to int in order to have original string form. for eg) 10:00 instead of 10:0
    if int(hour) > 12:
        return '{}:{} p.m.'.format((int(hour) - 12), minute)
    elif int(hour) == 12:
        return '12:{} p.m.'.format(minute)
    elif int(hour) == 0:
        return '12:{} a.m.'.format(minute)

    return '{}:{} a.m.'.format(hour, minute)
def build_available_time_string(availabilities):
    """
    Build a string eliciting for a possible time slot among at least two availabilities.
    """
    prefix = 'We have availabilities at '
    if len(availabilities) > 3:
        prefix = 'We have plenty of availability, including '

    prefix += build_time_output_string(availabilities[0])
    if len(availabilities) == 2:
        return '{} and {}'.format(prefix, build_time_output_string(availabilities[1]))

    return '{}, {} and {}'.format(prefix, build_time_output_string(availabilities[1]), build_time_output_string(availabilities[2]))
def save_dynamodb(appointment_type,date,time,end):
    client = boto3.client('dynamodb')
    tableName='Appointments'
    appId = str(uuid.uuid4())
    item = {
     'AppointmentType':{'S':appointment_type},
     'Date':  {'S':date},
     'Time':  {'S':time},
     'End':   {'S':end},
     'AppID': {'S':appId}
    }
    client.put_item(TableName=tableName, Item=item)
    
def make_appointment(intent_request):
    appointment_types=get_appointmentType()
    appointment_type = intent_request['currentIntent']['slots']['AppointmentType']
    date = intent_request['currentIntent']['slots']['Date']
    time = intent_request['currentIntent']['slots']['Time']
    source = intent_request['invocationSource']
    output_session_attributes = intent_request['sessionAttributes']
    booking_map = json.loads(try_ex(lambda: output_session_attributes['bookingMap']) or '{}')
    if source == 'DialogCodeHook':
        slots = intent_request['currentIntent']['slots']
        
        if not appointment_type:
            return elicit_slot(
                output_session_attributes,
                intent_request['currentIntent']['name'],
                intent_request['currentIntent']['slots'],
                'AppointmentType',
                {'contentType': 'PlainText', 'content': 'What type of appointment would you like to schedule?'},
                build_response_card(
                    'Specify Appointment Type', 'What type of appointment would you like to schedule?',
                    build_options('AppointmentType', appointment_types,appointment_type,date,None)
                )
            )
        validation_result = validate_book_appointment(appointment_types,appointment_type, date, time)
        if not validation_result['isValid']:
            slots[validation_result['violatedSlot']] = None
            return elicit_slot(
                output_session_attributes,
                intent_request['currentIntent']['name'],
                slots,
                validation_result['violatedSlot'],
                validation_result['message'],
                build_response_card(
                    'Specify {}'.format(validation_result['violatedSlot']),
                    validation_result['message']['content'],
                    build_options(validation_result['violatedSlot'], appointment_types,appointment_type,date,booking_map)
                )
            )
        if appointment_type and not date:
            return elicit_slot(
                output_session_attributes,
                intent_request['currentIntent']['name'],
                intent_request['currentIntent']['slots'],
                'Date',
                {'contentType': 'PlainText', 'content': 'When would you like to schedule your {}?'.format(appointment_type)},
                build_response_card(
                    'Specify Date',
                    'When would you like to schedule your {}?'.format(appointment_type),
                    build_options('Date', appointment_types,appointment_type,date,None)
                )
            )
        if appointment_type and date:
            booking_availabilities = try_ex(lambda: booking_map[date])
            if booking_availabilities is None:
                booking_availabilities = get_availabilities(date)
                booking_map[date] = booking_availabilities
                output_session_attributes['bookingMap'] = json.dumps(booking_map)
            
            duration=get_duration(appointment_types,appointment_type)
            appointment_type_availabilities =get_availabilities_for_duration(duration,booking_availabilities)
            if len(appointment_type_availabilities) == 0:
                # No availability on this day at all; ask for a new date and time.
                slots['Date'] = None
                slots['Time'] = None
                return elicit_slot(
                    output_session_attributes,
                    intent_request['currentIntent']['name'],
                    slots,
                    'Date',
                    {'contentType': 'PlainText', 'content': 'We do not have any availability on that date, is there another day which works for you?'},
                    build_response_card(
                        'Specify Date',
                        'What day works best for you?',
                        build_options('Date', appointment_types,appointment_type,date,booking_map)
                    )
                )
            message_content = 'What time on {} works for you? '.format(date)
            if time:
                if time in appointment_type_availabilities:
                    return delegate(output_session_attributes, slots)
                message_content = 'The time you requested is not available. '
                
            if len(appointment_type_availabilities) == 1:
                # If there is only one availability on the given date, try to confirm it.
                #time=str(appointment_type_availabilities[0].hour)+':'+str(appointment_type_availabilities[0].minute)
                time=str(appointment_type_availabilities[0].time())[0:5]
                slots['Time'] = time
                return confirm_intent(
                    output_session_attributes,
                    intent_request['currentIntent']['name'],
                    slots,
                    {
                        'contentType': 'PlainText',
                        'content': '{}{} is our only availability, does that work for you?'.format
                                   (message_content, build_time_output_string(time))
                    },
                    build_response_card(
                        'Confirm Appointment',
                        'Is {} on {} okay?'.format(build_time_output_string(time), date),
                        [{'text': 'yes', 'value': 'yes'}, {'text': 'no', 'value': 'no'}]
                    )
                )
            available_time_string = build_available_time_string(appointment_type_availabilities)
            return elicit_slot(
                output_session_attributes,
                intent_request['currentIntent']['name'],
                slots,
                'Time',
                {'contentType': 'PlainText', 'content': '{}{}'.format(message_content, available_time_string)},
                build_response_card(
                    'Specify Time',
                    'What time works best for you?',
                    build_options('Time', appointment_types,appointment_type,date,booking_map)
                )
            )
        return delegate(output_session_attributes, slots)
    elif source == 'FulfillmentCodeHook':
        duration=get_duration(appointment_types,appointment_type)
        delta=timedelta(minutes=int(duration))
        end_time=datetime.strptime(date+" "+time, '%Y-%m-%d %H:%M')
        end_time=str((end_time+delta).time())[0:5]
        save_dynamodb(appointment_type,date,time,end_time)
        booking_availabilities = get_availabilities(date)
        booking_map[date] = booking_availabilities
        output_session_attributes['bookingMap'] = json.dumps(booking_map)
    return close(
        output_session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Okay, I have booked your appointment.  We will see you at {} on {}'.format(build_time_output_string(time), date)
        }
    )
""" --- Intents --- """


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'MakeAppointment':
        return make_appointment(intent_request)
    raise Exception('Intent with name ' + intent_name + ' not supported')

def lambda_handler(event, context):
    
    logger.debug('event.bot.name={}'.format(event['bot']['name']))    
    return dispatch(event)