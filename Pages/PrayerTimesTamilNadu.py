import streamlit as st
from datetime import date, datetime, timedelta
import calendar
import math
import re
import pandas as pd

# Assuming PrayTimes class is defined here or imported from praytimes.py

class PrayTimes():


	#------------------------ Constants --------------------------
	#Dhuhr
 	#Asr Shafi
  	#Asr Hanafi
   	#Magrib and Iftar
	#Isha Shafi
 	#Isha Hanafi
  	#Fajr
   	#Imsak
	#Sunrise
 	#Midnight
  	#Noon

	# Time Names
	timeNames = {
		'imsak'    : 'Imsak',
		'fajr'     : 'Fajr',
		'sunrise'  : 'Sunrise',
		'dhuhr'    : 'Dhuhr',
		'asr'      : 'Asr',
		'sunset'   : 'Sunset',
		'maghrib'  : 'Maghrib',
		'isha'     : 'Isha',
		'midnight' : 'Midnight'
	}

	# Calculation Methods	
	methods = {
		'MWL': {
			'name': 'Muslim World League',
			'params': { 'fajr': 18, 'isha': 17 } },
		'ISNA': {
			'name': 'Islamic Society of North America (ISNA)',
			'params': { 'fajr': 15, 'isha': 15 } },
		'Egypt': {
			'name': 'Egyptian General Authority of Survey',
			'params': { 'fajr': 19.5, 'isha': 17.5 } },
		'Makkah': {
			'name': 'Umm Al-Qura University, Makkah',
			'params': { 'fajr': 18.5, 'isha': '90 min' } },  # fajr was 19 degrees before 1430 hijri
		'Karachi': {
			'name': 'University of Islamic Sciences, Karachi',
			'params': { 'fajr': 18, 'isha': 18 } },
		'Tehran': {
			'name': 'Institute of Geophysics, University of Tehran',
			'params': { 'fajr': 17.7, 'isha': 14, 'maghrib': 4.5, 'midnight': 'Jafari' } },  # isha is not explicitly specified in this method
		'Jafari': {
			'name': 'Shia Ithna-Ashari, Leva Institute, Qum',
			'params': { 'fajr': 16, 'isha': 14, 'maghrib': 4, 'midnight': 'Jafari' } },
		'TN': {
			'name': 'Tamil Nadu',
			'params': { 'fajr': 18, 'isha': 18} }
	}

	# Default Parameters in Calculation Methods
	defaultParams = {
		'maghrib': '0 min', 'midnight': 'Standard'
	}


	#---------------------- Default Settings --------------------

	calcMethod = 'MWL'

	# do not change anything here; use adjust method instead
	settings = {
		"imsak"    : '20 min',
		"dhuhr"    : '15 min',
		"asr"      : 'Standard',
		"highLats" : 'NightMiddle'
	}

	timeFormat = '24h'
	timeSuffixes = ['am', 'pm']
	invalidTime =  '-----'

	numIterations = 1
	offset = {}


	#---------------------- Initialization -----------------------

	def __init__(self, method = "MWL") :

		# set methods defaults
		for method, config in self.methods.items():
			for name, value in self.defaultParams.items():
				if not name in config['params'] or config['params'][name] is None:
					config['params'][name] = value

		# initialize settings
		self.calcMethod = method if method in self.methods else 'MWL'
		params = self.methods[self.calcMethod]['params']
		for name, value in params.items():
			self.settings[name] = value

		# init time offsets
		for name in self.timeNames:
			self.offset[name] = 0


	#-------------------- Interface Functions --------------------

	def setMethod(self, method):
		if method in self.methods:
			self.adjust(self.methods[method]['params'])
			self.calcMethod = method

	def adjust(self, params):
		self.settings.update(params)

	def tune(self, timeOffsets):
		self.offsets.update(timeOffsets)

	def getMethod(self):
		return self.calcMethod

	def getSettings(self):
		return self.settings

	def getOffsets(self):
		return self.offset

	def getDefaults(self):
		return self.methods

	# return prayer times for a given date
	def getTimes(self, date, coords, timezone, dst = 0, format = None):
		self.lat = coords[0]
		self.lng = coords[1]
		self.elv = coords[2] if len(coords)>2 else 0
		if format != None:
			self.timeFormat = format
		if type(date).__name__ == 'date':
			date = (date.year, date.month, date.day)
		self.timeZone = timezone + (1 if dst else 0)
		self.jDate = self.julian(date[0], date[1], date[2]) - self.lng / (15 * 24.0)
		return self.computeTimes()

	# convert float time to the given format (see timeFormats)
	def getFormattedTime(self, time, format, suffixes = None):
		if math.isnan(time):
			return self.invalidTime
		if format == 'Float':
			return time
		if suffixes == None:
			suffixes = self.timeSuffixes

		time = self.fixhour(time+ 0.5/ 60)  # add 0.5 minutes to round
		hours = math.floor(time)

		minutes = math.floor((time- hours)* 60)
		suffix = suffixes[ 0 if hours < 12 else 1 ] if format == '12h' else ''
		formattedTime = "%02d:%02d" % (hours, minutes) if format == "24h" else "%d:%02d" % ((hours+11)%12+1, minutes)
		return formattedTime + suffix


	#---------------------- Calculation Functions -----------------------

	# compute mid-day time
	def midDay(self, time):
		eqt = self.sunPosition(self.jDate + time)[1]
		return self.fixhour(12 - eqt)

	# compute the time at which sun reaches a specific angle below horizon
	def sunAngleTime(self, angle, time, direction = None):
		try:
			decl = self.sunPosition(self.jDate + time)[0]
			noon = self.midDay(time)
			t = 1/15.0* self.arccos((-self.sin(angle)- self.sin(decl)* self.sin(self.lat))/
					(self.cos(decl)* self.cos(self.lat)))
			return noon+ (-t if direction == 'ccw' else t)
		except ValueError:
			return float('nan')

	# compute asr time
	def asrTime(self, factor, time):
		decl = self.sunPosition(self.jDate + time)[0]
		angle = -self.arccot(factor + self.tan(abs(self.lat - decl)))
		return self.sunAngleTime(angle, time)

	# compute declination angle of sun and equation of time
	# Ref: http://aa.usno.navy.mil/faq/docs/SunApprox.php
	def sunPosition(self, jd):
		D = jd - 2451545.0
		g = self.fixangle(357.529 + 0.98560028* D)
		q = self.fixangle(280.459 + 0.98564736* D)
		L = self.fixangle(q + 1.915* self.sin(g) + 0.020* self.sin(2*g))

		R = 1.00014 - 0.01671*self.cos(g) - 0.00014*self.cos(2*g)
		e = 23.439 - 0.00000036* D

		RA = self.arctan2(self.cos(e)* self.sin(L), self.cos(L))/ 15.0
		eqt = q/15.0 - self.fixhour(RA)
		decl = self.arcsin(self.sin(e)* self.sin(L))

		return (decl, eqt)

	# convert Gregorian date to Julian day
	# Ref: Astronomical Algorithms by Jean Meeus
	def julian(self, year, month, day):
		if month <= 2:
			year -= 1
			month += 12
		A = math.floor(year / 100)
		B = 2 - A + math.floor(A / 4)
		return math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + B - 1524.5



	#---------------------- Compute Prayer Times -----------------------

	# compute prayer times at given julian date
	def computePrayerTimes(self, times):
		times = self.dayPortion(times)
		params = self.settings

		imsak   = self.sunAngleTime(self.eval(params['imsak']), times['imsak'], 'ccw')
		fajr    = self.sunAngleTime(self.eval(params['fajr']), times['fajr'], 'ccw')
		sunrise = self.sunAngleTime(self.riseSetAngle(self.elv), times['sunrise'], 'ccw')
		dhuhr   = self.midDay(times['dhuhr'])
		asr     = self.asrTime(self.asrFactor(params['asr']), times['asr'])
		sunset  = self.sunAngleTime(self.riseSetAngle(self.elv), times['sunset'])
		maghrib = self.sunAngleTime(self.eval(params['maghrib']), times['maghrib'])
		isha    = self.sunAngleTime(self.eval(params['isha']), times['isha'])
		return {
			'imsak': imsak, 'fajr': fajr, 'sunrise': sunrise, 'dhuhr': dhuhr,
			'asr': asr, 'sunset': sunset, 'maghrib': maghrib, 'isha': isha
		}

	# compute prayer times
	def computeTimes(self):
		times = {
			'imsak': 5, 'fajr': 5, 'sunrise': 6, 'dhuhr': 12,
			'asr': 13, 'sunset': 18, 'maghrib': 18, 'isha': 18
		}
		# main iterations
		for i in range(self.numIterations):
			times = self.computePrayerTimes(times)
		times = self.adjustTimes(times)
		# add midnight time
		if self.settings['midnight'] == 'Jafari':
			times['midnight'] = times['sunset'] + self.timeDiff(times['sunset'], times['fajr']) / 2
		else:
			times['midnight'] = times['sunset'] + self.timeDiff(times['sunset'], times['sunrise']) / 2

		times = self.tuneTimes(times)
		return self.modifyFormats(times)

	# adjust times in a prayer time array
	def adjustTimes(self, times):
		params = self.settings
		tzAdjust = self.timeZone - self.lng / 15.0
		for t,v in times.items():
			times[t] += tzAdjust

		if params['highLats'] != 'None':
			times = self.adjustHighLats(times)

		if self.isMin(params['imsak']):
			times['imsak'] = times['fajr'] - self.eval(params['imsak']) / 60.0
		# need to ask about 'min' settings
		if self.isMin(params['maghrib']):
			times['maghrib'] = times['sunset'] - self.eval(params['maghrib']) / 60.0

		if self.isMin(params['isha']):
			times['isha'] = times['maghrib'] - self.eval(params['isha']) / 60.0
		times['dhuhr'] += self.eval(params['dhuhr']) / 60.0

		return times

	# get asr shadow factor
	def asrFactor(self, asrParam):
		methods = {'Standard': 1, 'Hanafi': 2}
		return methods[asrParam] if asrParam in methods else self.eval(asrParam)

	# return sun angle for sunset/sunrise
	def riseSetAngle(self, elevation = 0):
		elevation = 0 if elevation == None else elevation
		return 0.833 + 0.0347 * math.sqrt(elevation) # an approximation

	# apply offsets to the times
	def tuneTimes(self, times):
		for name, value in times.items():
			times[name] += self.offset[name] / 60.0
		return times

	# convert times to given time format
	def modifyFormats(self, times):
		for name, value in times.items():
			times[name] = self.getFormattedTime(times[name], self.timeFormat)
		return times

	# adjust times for locations in higher latitudes
	def adjustHighLats(self, times):
		params = self.settings
		nightTime = self.timeDiff(times['sunset'], times['sunrise']) # sunset to sunrise
		times['imsak'] = self.adjustHLTime(times['imsak'], times['sunrise'], self.eval(params['imsak']), nightTime, 'ccw')
		times['fajr']  = self.adjustHLTime(times['fajr'], times['sunrise'], self.eval(params['fajr']), nightTime, 'ccw')
		times['isha']  = self.adjustHLTime(times['isha'], times['sunset'], self.eval(params['isha']), nightTime)
		times['maghrib'] = self.adjustHLTime(times['maghrib'], times['sunset'], self.eval(params['maghrib']), nightTime)
		return times

	# adjust a time for higher latitudes
	def adjustHLTime(self, time, base, angle, night, direction = None):
		portion = self.nightPortion(angle, night)
		diff = self.timeDiff(time, base) if direction == 'ccw' else self.timeDiff(base, time)
		if math.isnan(time) or diff > portion:
			time = base + (-portion if direction == 'ccw' else portion)
		return time

	# the night portion used for adjusting times in higher latitudes
	def nightPortion(self, angle, night):
		method = self.settings['highLats']
		portion = 1/2.0  # midnight
		if method == 'AngleBased':
			portion = 1/60.0 * angle
		if method == 'OneSeventh':
			portion = 1/7.0
		return portion * night

	# convert hours to day portions
	def dayPortion(self, times):
		for i in times:
			times[i] /= 24.0
		return times


	#---------------------- Misc Functions -----------------------

	# compute the difference between two times
	def timeDiff(self, time1, time2):
		return self.fixhour(time2- time1)

	# convert given string into a number
	def eval(self, st):
		val = re.split('[^0-9.+-]', str(st), 1)[0]
		return float(val) if val else 0

	# detect if input contains 'min'
	def isMin(self, arg):
		return isinstance(arg, str) and arg.find('min') > -1


	#----------------- Degree-Based Math Functions -------------------

	def sin(self, d): return math.sin(math.radians(d))
	def cos(self, d): return math.cos(math.radians(d))
	def tan(self, d): return math.tan(math.radians(d))

	def arcsin(self, x): return math.degrees(math.asin(x))
	def arccos(self, x): return math.degrees(math.acos(x))
	def arctan(self, x): return math.degrees(math.atan(x))

	def arccot(self, x): return math.degrees(math.atan(1.0/x))
	def arctan2(self, y, x): return math.degrees(math.atan2(y, x))

	def fixangle(self, angle): return self.fix(angle, 360.0)
	def fixhour(self, hour): return self.fix(hour, 24.0)

	def fix(self, a, mode):
		if math.isnan(a):
			return a
		a = a - mode * (math.floor(a / mode))
		return a + mode if a < 0 else a

def adjust_time(time_str, minutes):
    # Ensure the AM/PM indicator is uppercase to match the expected format
    time_str_upper = time_str.upper()
    
    # Convert time string to a datetime object, accounting for AM/PM
    time_obj = datetime.strptime(time_str_upper, '%I:%M%p')  # Adjusted to remove space for compatibility

    # Add the minutes
    adjusted_time = time_obj + timedelta(minutes=minutes)

    # Return the adjusted time in 'HH:MM AM/PM' format
    return adjusted_time.strftime('%I:%M %p')

def adjust_time_negative(time_str, minutes):
    # Ensure the AM/PM indicator is uppercase to match the expected format
    time_str_upper = time_str.upper()
    
    # Convert time string to a datetime object, accounting for AM/PM
    time_obj = datetime.strptime(time_str_upper, '%I:%M%p')  # Adjusted to remove space for compatibility

    # Add the minutes
    adjusted_time = time_obj - timedelta(minutes=minutes)

    # Return the adjusted time in 'HH:MM AM/PM' format
    return adjusted_time.strftime('%I:%M %p')

def calculate_prayer_times_for_month(year, month):
    latitude = 11.495351
    longitude = 79.759439
    timezone = 5.5
    dst = False
    calc_method = 'MWL'
    
    PT = PrayTimes(calc_method)
    PT.timeFormat = '12h'  # Using 12-hour format

    num_days = calendar.monthrange(year, month)[1]
    prayer_times = []

    for day in range(1, num_days + 1):
        date_str = datetime(year, month, day).strftime('%d/%m/%Y')
        
        # Calculate times using standard Asr calculation
        PT.adjust({'asr': 'Standard'})
        times_standard = PT.getTimes((year, month, day), (latitude, longitude, 0), timezone, dst)
        asr_shafi_time = adjust_time(times_standard['asr'], 5)  # Adding 5 minutes to Asr Standard

        # Calculate times using Hanafi Asr calculation
        PT.adjust({'asr': 'Hanafi'})
        times_hanafi = PT.getTimes((year, month, day), (latitude, longitude, 0), timezone, dst)
        asr_hanafi_time = adjust_time(times_hanafi['asr'], 2)  # Adding 2 minutes to Asr Hanafi

        prayer_times.append({
            'Date': date_str,
            'Dhuhr': times_standard['dhuhr'],
            'Asr Shafi': asr_shafi_time,
            'Asr Hanafi': asr_hanafi_time,
            'Magrib and Iftar': adjust_time(times_standard['sunset'], 9),  # Adding 9 minutes to Sunset
            'Isha Shafi': adjust_time(times_standard['isha'], 12),  # Adding 12 minutes
			'Fajr': times_standard['fajr'],
            'Imsak': times_standard['imsak'],
            'Sunrise': times_standard['sunrise'],
            'Sunset': times_standard['sunset'],
            'Noon': adjust_time_negative(times_standard['dhuhr'], 15)
        })
    
    return pd.DataFrame(prayer_times)


def calculate_prayer_times_for_year(year):
    latitude = 11.495351
    longitude = 79.759439
    timezone = 5.5
    dst = False
    calc_method = 'MWL'
    
    PT = PrayTimes(calc_method)
    PT.timeFormat = '12h'  # Using 12-hour format
    yearly_prayer_times = []

    for month in range(1, 13):
        num_days = calendar.monthrange(year, month)[1]
        for day in range(1, num_days + 1):
            date_str = datetime(year, month, day).strftime('%d/%m/%Y')
            
            # Calculate times using standard Asr calculation
            PT.adjust({'asr': 'Standard'})
            times_standard = PT.getTimes((year, month, day), (latitude, longitude, 0), timezone, dst)
            asr_shafi_time = adjust_time(times_standard['asr'], 5)  # Adding 5 minutes to Asr Standard

            # Calculate times using Hanafi Asr calculation
            PT.adjust({'asr': 'Hanafi'})
            times_hanafi = PT.getTimes((year, month, day), (latitude, longitude, 0), timezone, dst)
            asr_hanafi_time = adjust_time(times_hanafi['asr'], 2)  # Adding 2 minutes to Asr Hanafi

            yearly_prayer_times.append({
                'Date': date_str,
                'Fajr': times_standard['fajr'],
                'Sunrise': times_standard['sunrise'],
                'Noon': adjust_time_negative(times_standard['dhuhr'], 15),
                'Asr Standard': asr_shafi_time,
                'Asr Hanafi': asr_hanafi_time,
                'Sunset': times_standard['sunset'],
				'Isha': adjust_time(times_standard['isha'], 12)
            })

    return pd.DataFrame(yearly_prayer_times)

# Streamlit UI setup
st.title('Prayer Times for PNO')

# User input for month selection
year = datetime.now().year
month = st.selectbox('Select Month:', range(1, 13), format_func=lambda x: datetime(year, x, 1).strftime('%B'))

if st.button('Show Prayer Times'):
    prayer_times_df = calculate_prayer_times_for_month(year, month)
    st.write(f"Prayer Times for {calendar.month_name[month]} {year}")
    st.dataframe(prayer_times_df)

if st.button('Export Yearly Prayer Times as CSV'):
    prayer_times_df = calculate_prayer_times_for_year(year)
    csv = prayer_times_df.to_csv(index=False)
    st.download_button(
        label="Download Yearly Prayer Times as CSV",
        data=csv,
        file_name=f"yearly_prayer_times_{year}.csv",
        mime='text/csv',
    )

    st.write(f"Prayer Times for the Year {year}")
    st.dataframe(prayer_times_df)