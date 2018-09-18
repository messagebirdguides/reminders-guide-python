# SMS Appointment Reminders
### ⏱ 15 min build time

## Why build SMS appointment reminders? 

Booking appointments online from a website or mobile app is quick and easy. Customers just have to select their desired date and time, enter their personal details and hit a button. The problem, however, is that easy-to-book appointments are often just as easy to forget.

For appointment-based services, no-shows are annoying and costly because of the time and revenue lost waiting for a customer instead of serving them, or another customer. Timely SMS reminders act as a simple and discrete nudges, which can go a long way in the prevention of costly no-shows.

## Getting Started

In this MessageBird Developer Guide, we'll show you how to use the MessageBird SMS messaging API to build an SMS appointment reminder application in Python. 

This sample application represents the order website of a fictitious online beauty salon called *BeautyBird*. To reduce the growing number of no-shows, BeautyBird now collects appointment bookings through a form on their website and schedules timely SMS reminders to be sent out three hours before the selected date and time.

To run the full sample application, head over to the [MessageBird Developer Guides GitHub repository](https://github.com/messagebirdguides/reminders-guide-python) to clone or download the source code as a ZIP archive. You will need Python 2 or 3 to run the sample application, the [Flask framework](http://flask.pocoo.org/) for making Python web applications, and the [pytz library](http://pytz.sourceforge.net/) for handling calculations with local timezones.

Now, to install the required packages, we use the Python package manager [pip](https://pypi.org/project/pip/). Let's open a console pointed at the directory into which you've placed the sample application and run the following commands to install the [MessageBird SDK for Node.js](https://www.npmjs.com/package/messagebird) and the libraries we mentioned above:

````bash
pip install messagebird
````
````bash
pip install flask
````
````bash
pip install pytz
````

## Configuring the MessageBird Client

The MessageBird API key needs to be provided as a parameter. API keys can be created or retrieved from the [API access (REST) tab](https://dashboard.messagebird.com/en/developers/access) in the _Developers_ section of your MessageBird account.


 **Pro-tip:** Hardcoding your credentials in the code is a risky practice that should never be used in production applications. A better method, also recommended by the [Twelve-Factor App Definition](https://12factor.net/), is to use environment variables. Our sample application stores the API key in a file named `config_file.cfg` that contains the following line:

````env
SECRET_KEY='YOUR-API-KEY'
````

When we initialize the application in `app.py`, we also tell it where to find configuration variables:

````python
app = Flask(__name__)
app.config.from_pyfile('config_file.cfg')
````

The MessageBird Python client is loaded with the following statement in `app.py`:

````python
client = messagebird.Client(app.config['SECRET_KEY'])
````
## Other Configuration Variables

We assume that BeautyBird's customers are all located in the same time zone (US Pacific Time in this application). We also assume that their phone numbers have the same country code, so that they do not have to enter a country code in the appointment form.

Since the time zone and country code apply throughout the application, we also define them in the configuration file `config_file.cfg`:

````env
COUNTRY_CODE='31'
TIMEZONE='Europe/Amsterdam'
````

Timezones should be specified as strings that exist in pytz's [list of timezones](http://pytz.sourceforge.net/#helpers). In `app.py`, we load the time zone into a variable as follows:

````python
local_time = timezone(app.config['TIMEZONE'])
````
We also define a datetime format that fits with the conventions of the customer's locality. In `config_file.cfg`, the following line specifies the datetime format the the customer will see in SMS messages and the confirmation page:

````env
DATETIME_FORMAT='%m-%d-%Y %I:%M%p'
````

We load this format into a variable in `app.py`:

````python
fmt = app.config['DATETIME_FORMAT']
````

## Collecting User Input

In order to send SMS messages to users, you need to collect their phone number as part of the booking process. We have created a sample form that asks the user for their name, desired treatment, number, date and time. For HTML forms it's recommended to use `type="tel"` for the phone number input. You can see the template for the complete form in the file `templates/index.html` and the route that drives it is defined as `@app.route('/', methods=['GET', 'POST'])` in `app.py`.

## Storing Appointments & Scheduling Reminders

The user's input is sent to the route `@app.route('/', methods=['GET', 'POST'])` defined in `app.py`. The implementation covers the following steps:

### Step 1: Check their input

Validate that the user has entered a value for every field in the form. The fields are all marked as `required` in `index.html` for this reason.

### Step 2: Check the appointment date and time

Confirm that the date and time are valid and at least three hours and five minutes in the future. BeautyBird won't take bookings on shorter notice. Also, since we want to schedule reminders three hours before the treatment, anything else doesn't make sense from a testing perspective. We use the [datetime](https://docs.python.org/2/library/datetime.html) library that comes with Python and the pytz library we installed earlier to convert the local time entered by customers into UTC time to avoid complications with daylight savings. Calculations are done in UTC, then converted back into local time in the reminder messages and confirmation page.

````python
if request.method=="POST":

    #retrieve date and time, and convert into python datetime object
    appt_date = datetime.strptime(request.form['appt-date'], '%Y-%m-%d')
    appt_time = datetime.strptime(request.form['appt-time'], '%H:%M').time()
    appointmentDT = datetime.combine(appt_date,appt_time)
    
    #create datetime with local timezone, then convert to UTC for arithmetic
    #converting to UTC for calculations avoids complications from daylight savings
    local_appointmentDT = local_time.localize(appointmentDT)
    utc_appointmentDT = local_appointmentDT.astimezone(pytz.utc)

    #calculate reminder time and convert to RFC 3339 format. RFC 3339 format is required for scheduling the message when submitting request to MessageBird client.
    utc_reminderDT = utc_appointmentDT - timedelta(hours=3)
    #removes extraneous '+00:00' from end of ISO string and appends 'Z' indicating UTC timezone.
    iso_reminderDT = utc_reminderDT.isoformat("T")[:-6] + 'Z' 

    #get current UTC time for checking that appointment date/time is at least 3:05 hours in future
    current_utc = pytz.utc.localize(datetime.utcnow())
    
    #check that date/time is at least 3:05 hours in the future; throw error if it isn't
    if (utc_appointmentDT - timedelta(hours=3, minutes=5) < current_utc):
        flash('Appointment time must be at least 3:05 hours from now')
        return render_template('index.html')
````

### Step 3: Check their phone number

Check whether the phone number is correct. This can be done with the [MessageBird Lookup API](https://developers.messagebird.com/docs/lookup#lookup-request), which takes a phone number entered by a user, validates the format and returns information about the number, such as whether it is a mobile or fixed line number. This API doesn't enforce a specific format for the number but rather understands a variety of different variants for writing a phone number, for example using different separator characters between digits, giving your users the flexibility to enter their number in various ways.

````python
#check if phone number entered is valid, using country code from config file:
try:
    lookup = client.lookup(app.config['COUNTRY_CODE'] + request.form['phone'])
    #If lookup is successful but returned phone number types don't include 'mobile', prompt for new number 
    if ('mobile' not in lookup.type):
        flash("The number you entered is not a mobile number. Please re-enter a mobile number.")
        return render_template('index.html')
````

We prepend the country code specified in the configuration file to the phone number the customer enters. Then we try submitting the request to the MessageBird API. If the lookup succeeds but the phone number types returned don't include "mobile", we flash an error message.

In our `except` statement, we specify what happens if the lookup fails. We handle the following cases:

* An error (code 21) occurred, which means MessageBird was unable to parse the phone number.
* Another error code occurred, which means something else went wrong in the API.

````python
except messagebird.client.ErrorException as e:
    if(e.errors[0].code == 21):
        flash('Please enter a valid phone number.')
    else:
        flash('Something went wrong while checking your phone number.')
	return render_template('index.html')
except: #miscellaneous exceptions
    flash('Something went wrong while checking your phone number.')
    return render_template('index.html')
````

In either case, we display an appropriate message at the top of the webpage. The area displaying error messages is defined in `templates/index.html`:

````html
<!--If form submission results in error, flash error message -->
{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul class=flashes>
    {% for message in messages %}
      <li>{{ message }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
````

### Step 4: Schedule the reminder

Earlier, we had calculated the time at which the reminder should be sent, and stored it in the variable `iso_reminderDT`. We will now use this in our call to
MessageBird's API:

````python
#if phone number and entered date/time are valid, submit to MessageBird client
try:
    verify = client.message_create('BeautyBird',
    								app.config['COUNTRY_CODE'] + request.form['phone'],
             						request.form['customer_name'] + ', you have an appointment at BeautyBird at ' + appointmentDT.strftime(fmt),
            						{'scheduledDatetime': iso_reminderDT})
````

Let's break down the parameters that are set with this call of `message.create()`:

- `BeautyBird`: The sender ID. You can use a mobile number here, or an alphanumeric ID, like in the example.
- `app.config['COUNTRY_CODE'] + request.form['phone']`: An array of phone numbers. We just need one number in this example.
- The body of the message that the customer will see. We format the datetime in this message according to the configuration variable specified in `config_file.cfg` and loaded into the `fmt` variables in `app.py`.
- `scheduledDatetime`: This instructs MessageBird not to send the message immediately but at a given timestamp, which we've defined previously as the variable `iso_reminderDT`.

### Step 5: Store the appointment

We're almost done! The application's logic continues in the `try` statement for the API call, where we store the appointment, then in an `except` statement to handle failed API calls:

````python
	#push the appointment to the list of appointments created earlier. In a production application, the appointment should be entered in a database.
	appointment = { 'name' : request.form['customer_name'],
	                'treatment': request.form['treatment'],
	                'number': request.form['phone'],
	                'appointmentDT': utc_appointmentDT,
	                'reminderDT': utc_reminderDT}
	appointment_list.append(appointment)
	#redirect the user to the confirmation page 
	return render_template('success.html', 
							name=request.form['customer_name'],
	                        treatment=request.form['treatment'],
	                        phone=request.form['phone'],
	                        appointmentDT=appointmentDT.strftime(fmt))
    
#on failure, flash error on webpage.
except messagebird.client.ErrorException as e:
for error in e.errors:
    flash('  description : %s\n' % error.description)
    return render_template('index.html')
````

As you can see, for the purpose of the sample application, we simply "persist" the appointment to a global list in memory. This is where, in practical applications, you would write the appointment to a persistence layer such as a file or database. We also show a confirmation page, which is defined in `templates/success.html`.

## Testing the Application

Now, let's run the following command from your console:

````bash
python app.py
````

Then, point your browser at http://localhost:5000/ to see the form and schedule your appointment! If you've used a live API key, a message will arrive to your phone three hours before the appointment! But don't actually leave the house, this is just a demo :)


## Nice work!

You now have a running SMS appointment reminder application!

You can now use the flow, code snippets and UI examples from this tutorial as an inspiration to build your own SMS reminder system. Don't forget to download the code from the [MessageBird Developer Guides GitHub repository](https://github.com/messagebirdguides/reminders-guide-python).

## Next steps

Want to build something similar but not quite sure how to get started? Please feel free to let us know at support@messagebird.com, we'd love to help!