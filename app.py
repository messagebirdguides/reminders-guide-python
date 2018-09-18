from flask import Flask, render_template, request, flash
import messagebird
import pytz
from pytz import timezone
from datetime import datetime, time, timedelta

#Configure the app as follows.
app = Flask(__name__)
app.config.from_pyfile('config_file.cfg')

#create instance of messagebird.Client using API key
client = messagebird.Client(app.config['SECRET_KEY'])

#set timezone that will be used by user. This app assumes all users will be in the same timezone.
#Timezone is set in config fie. See pytz documentation for list of timezones supported.
local_time = timezone(app.config['TIMEZONE'])

#determine format of datetime that customer will see in SMS and confirmation page.
fmt = app.config['DATETIME_FORMAT']

#array to store all appointments. In a production application, the appointments should be stored in a database instead.
appointment_list = []

#Route for the appointment form. Determines what happens when form is submitted.
@app.route('/', methods=['GET', 'POST'])
def makeAppointment():
    
    #when form is submitted, calculate times
    if request.method=="POST":

        #retrieve date and time, and convert into python datetime object
        appt_date = datetime.strptime(request.form['appt-date'], '%Y-%m-%d')
        appt_time = datetime.strptime(request.form['appt-time'], '%H:%M').time()
        appointmentDT = datetime.combine(appt_date,appt_time)
        
        #create datetime with local timezone, then convert to UTC for arithmetic
        #converting to UTC for calculations avoids complications from daylight savings
        local_appointmentDT = local_time.localize(appointmentDT)
        utc_appointmentDT = local_appointmentDT.astimezone(pytz.utc)

        #calculate reminder time and convert to ISO. This is required for scheduling the message later.
        utc_reminderDT = utc_appointmentDT - timedelta(hours=3)
        #removes extraneous '+00:00' from end of ISO string and appends 'Z' indicating UTC timezone.
        iso_reminderDT = utc_reminderDT.isoformat("T")[:-6] + 'Z'

        #get current UTC time for checking that appointment date/time is at least 3:05 hours in future
        current_utc = pytz.utc.localize(datetime.utcnow())
        
        #check that date/time is at least 3:05 hours in the future; throw error if it isn't
        if (utc_appointmentDT - timedelta(hours=3, minutes=5) < current_utc):
            flash('Appointment time must be at least 3:05 hours from now')
            return render_template('index.html')

        #check if phone number entered is valid, using country code from config file:
        try:
            lookup = client.lookup(app.config['COUNTRY_CODE'] + request.form['phone'])
            #If lookup is successful but returned phone number types don't include 'mobile', prompt for new number
            if ('mobile' not in lookup.type):
                flash("The number you entered is not a mobile number. Please re-enter a mobile number.")
                return render_template('index.html')
        except messagebird.client.ErrorException as e:
            if(e.errors[0].code == 21):
                flash('Please enter a valid phone number.')
            else:
                flash('Something went wrong while checking your phone number.')
            return render_template('index.html')
        except: #miscellaneous exceptions
            flash('Something went wrong while checking your phone number.')
            return render_template('index.html')
            
        #if phone number and entered date/time are valid, submit to MessageBird client
        try:
            verify = client.message_create('BeautyBird', app.config['COUNTRY_CODE'] + request.form['phone'],
                                            request.form['customer_name'] + ', you have an appointment at BeautyBird at ' + appointmentDT.strftime(fmt),
                                           {'scheduledDatetime': iso_reminderDT})
        #push the appointment to the list of appointments created earlier. In a production application, the appointment should be entered in a database.
            appointment = { 'name' : request.form['customer_name'],
                            'treatment': request.form['treatment'],
                            'number': request.form['phone'],
                            'appointmentDT': utc_appointmentDT,
                            'reminderDT': utc_reminderDT}
            appointment_list.append(appointment)
            #redirect the user to the confirmation page 
            return render_template('success.html', name=request.form['customer_name'],
                                               treatment=request.form['treatment'],
                                               phone=request.form['phone'],
                                               appointmentDT=appointmentDT.strftime(fmt))        
        #on failure, flash error on webpage.
        except messagebird.client.ErrorException as e:
            for error in e.errors:
                flash('  description : %s\n' % error.description)
                return render_template('index.html')            


    return render_template('index.html')

if __name__ == '__main__':
    app.run()
