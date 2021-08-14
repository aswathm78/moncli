import json, pytz, importlib, re
import pytz
from datetime import datetime, timedelta
from enum import Enum

from pycountry import countries
from schematics.exceptions import ConversionError, ValidationError
from schematics.types import BaseType

from . import client
from .entities import column_value as cv
from .enums import PeopleKind
from .models import MondayModel

DATE_FORMAT = '%Y-%m-%d'
TIME_FORMAT = '%H:%M:%S'
ZULU_FORMAT = '{}T{}.%fZ'.format(DATE_FORMAT, TIME_FORMAT)


class MondayType(BaseType):

    null_value = None
    allow_casts = ()

    def __init__(self, id: str = None, title: str = None, *args, **kwargs):
        self.original_value = None
        metadata = {}

        if not id and not title:
            raise TypeError('"id" or "title" parameter is required.')
        if id:
            metadata['id'] = id
        if title:
            metadata['title'] = title

        super(MondayType, self).__init__(*args, metadata=metadata, **kwargs)

    @property
    def changed_at(self):
        value = self.metadata.get('changed_at', None)
        if not value:
            return None
        changed_at = datetime.strptime(value, ZULU_FORMAT)
        utc = pytz.timezone('UTC')
        changed_at = utc.localize(changed_at, is_dst=False)
        return changed_at.astimezone(datetime.now().astimezone().tzinfo)

    def to_native(self, value, context=None):
        if not value:
            return value

        if not isinstance(value, cv.ColumnValue):
            if self.allow_casts and isinstance(value, self.allow_casts):
                return self._cast(value)
            return value

        self.metadata['id'] = value.id
        self.metadata['title'] = value.title
        settings = json.loads(value.settings_str) if value.settings_str else {}
        for k, v in settings.items():
            self.metadata[k] = v

        loaded_value = json.loads(value.value)
        self._extract_metadata(loaded_value)
        try:
            additional_info = json.loads(value.additional_info)
        except:
            additional_info = value.additional_info
        self.original_value = self._convert((value.text, loaded_value, additional_info))
        return self.original_value

    def to_primitive(self, value, context=None):
        if self.null_value == None:
            return None
        if not value:
            return self.null_value
        return self._export(value)

    def value_changed(self, value, other):
        if (value and not other) or (other and not value):
            return True
        return self._compare(value, other)

    def _cast(self, value):
        return self.native_type(value)

    def _extract_metadata(self, value):
        try:
            self.metadata['changed_at'] = value.pop('changed_at', None)
        except:
            pass

    def _convert(self, value: tuple):
        _, data, _ = value
        return data

    def _export(self, value):
        return value

    def _compare(self, value, other):
        return value != other


class MondaySimpleType(MondayType):

    null_value = ''


class MondayComplexType(MondayType):

    null_value = {}


class ComplexTypeValue():

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        for k, v in self.__dict__.items():
            if v != getattr(other, k):
                return False
        return True


class CheckboxType(MondayComplexType):

    native_type = bool
    primitive_type = dict
    allow_casts = (str, int)

    def __init__(self, id: str = None, title: str = None, *args, **kwargs):
        super().__init__(id=id, title=title, default=False, *args, **kwargs)

    def validate_checkbox(self, value):
        if isinstance(value, self.allow_casts):
            value = self._cast(value)
        if type(value) is not bool:
            raise ValidationError('Value is not a valid checkbox type: ({}).'.format(value))

    def _convert(self, value: tuple):
        _, value, _ = value
        try:
            return bool(value['checked'])
        except:
            return False

    def _export(self, value):
        return {'checked': 'true'}


class CountryType(MondayComplexType):

    class Country(ComplexTypeValue):

        def __init__(self, name, code):
            self.name = name
            self.code = code

    native_type = Country
    primitive_type = dict

    def validate_country(self, value):
        if value.code:
            country = countries.get(alpha_2=value.code)
            if not country:
                raise ValidationError('Invalid country code: "{}".'.format(value.code))
        if value.name:
            country = countries.get(name=value.name)
            if not country:
                raise ValidationError('Invalid country name: "{}".'.format(value.code))

    def _convert(self, value: tuple):
        _, value, _ = value
        if value == self.null_value:
            return self.native_type()
        return self.Country(
            value['countryName'],
            value['countryCode'])

    def _export(self, value):
        if value.code and value.name:
            return {
                'countryCode': value.code,
                'countryName': value.name
            }
        return self.null_value

class DateType(MondayComplexType):

    native_type = datetime
    primitive_type = dict

    def validate_date(self, value):
        if not isinstance(value, self.native_type):
            raise ValidationError('Invalid datetime type.')

    def _convert(self, value: tuple):
        _, value, _ = value
        try:
            date = datetime.strptime(value['date'], DATE_FORMAT) 
        except:
            return None

        try:
            if value['time'] != None:
                date = pytz.timezone('UTC').localize(date)
                time = datetime.strptime(value['time'], TIME_FORMAT)
                date = date + timedelta(hours=time.hour, minutes=time.minute, seconds=time.second)
                return date.astimezone(datetime.now().astimezone().tzinfo)
        except:
            pass

        return date

    def _export(self, value):
        # Verify if time value exists before utc conversion.
        time = datetime.strftime(value, TIME_FORMAT)
        if time == '00:00:00':
            time = None
        value = value.astimezone(pytz.timezone('UTC'))
        date = datetime.strftime(value, DATE_FORMAT)   
        if time:
            time = datetime.strftime(value, TIME_FORMAT)

        return {
            'date': date,
            'time': time
        }


class DropdownType(MondayComplexType):

    native_type = list
    primitive_type = dict
    allow_casts = (str, Enum)

    def __init__(self, id: str = None, title: str = None, data_mapping: dict = None, *args, **kwargs):
        if data_mapping:
            self._data_mapping = data_mapping
            self.choices = data_mapping.values()
        super(DropdownType, self).__init__(id=id, title=title, *args, default=[], **kwargs)

    def validate_dropdown(self, value):
        if self._data_mapping:
            reverse = {v: k for k, v in self._data_mapping.items()}
            value = [reverse[label] for label in value]
        labels = [label['name'] for label in self.metadata['labels']]
        for label in value:
            if label not in labels:
                raise ValidationError('Unable to find index for status label: ({}).'.format(value))

    def _cast(self, value):
        return [value]

    def _convert(self, value: tuple):
        text, _, _ = value
        try:
            labels = text.split(', ')
        except:
            return self.default

        if not self._data_mapping:
            self.choices = labels
            return labels
        try:
            return [self._data_mapping[text] for text in labels]
        except:
            return self.default

    def _export(self, value):
        if self._data_mapping:
            reverse = {v: k for k, v in self._data_mapping.items()}
            value = [reverse[label] for label in value]
        ids = []
        for label in self.metadata['labels']:
            if value == label['name'] or label['name'] in value:
                ids.append(label['id'])
        return {'ids': ids}
        

class EmailType(MondayComplexType):

    class Email(ComplexTypeValue):

        def __init__(self, email: str, text: str = None):
            self.email = email
            if not text:
                text = email
            self.text = text

    native_type = Email
    primitive_type = dict

    def validate_email(self, value):
        if not isinstance(value, self.Email):
            raise ValidationError('Expected value of type "Email", received "{}" instead.'.format(value.__class__.__name__))
        regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if value.email and not re.fullmatch(regex, value.email):
            raise ValidationError('Email.email cannot be null or an invalid email.')
        
    def _convert(self, value):
        _, value, _ = value
        if value == self.null_value:
            return self.native_type()
        return self.native_type(
            value['email'],
            value['text'])

    def _export(self, value):
        if not value.email:
            return self.null_value
        return {
            'email': self.email,
            'text': self.text
        }


class ItemLinkType(MondayComplexType):

    native_type = list
    primitive_type = dict

    def __init__(self, id: str = None, title: str = None, multiple_values: bool = True, *args, **kwargs):
        super().__init__(id=id, title=title, *args, **kwargs)
        if not multiple_values:
            self.native_type = str
        self.metadata['allowMultipleItems'] = multiple_values 

    @property
    def multiple_values(self):
        return self.metadata['allowMultipleValues']

    def validate_itemlink(self, value):
        if not self.multiple_values:
            if value != None and type(value) == list:
                raise ValidationError('Multiple items for this item link property are not supported.')
        else:
            if value and type(value) != list:
                raise ValidationError('Item link property requires a list value for multiple items.')

    def _convert(self, value: tuple):
        _, value, _ = value
        try:
            ids = [id['linkedPulseId'] for id in value['linkedPulseIds']]
        except:
            ids = []
        
        if not self.multiple_values:
            try:
                return str(ids[0])
            except:
                return None

        return [str(value) for value in ids]

    def _export(self, value):
        if value == None:
            value = []
        if type(value) is not list:
            return {'item_ids': [int(value)]}
        return {'item_ids': [int(val) for val in value]}

    def _compare(self, value, other):
        if not self.multiple_values:
            return super()._compare(value, other)
        if len(value) != len(other):
            return False
        for val in value:
            if val not in other:
                return False
        return True


class LongTextType(MondayComplexType):

    native_type = str
    primitive_type = dict

    def validate_text(self, value):
        if type(value) is not str:
            raise ValidationError('Value is not a valid long text type: ({}).'.format(value))

    def value_changed(self, value):
        if self._null_value_change(value):
            return True
        return self.original_value['text'] != value['text']

    def _convert(self, value: tuple):
        _, value, _ = value
        if value == self.null_value:
            return None
        return value['text']

    def _export(self, value):
        if not value: 
            return self.null_value
        return {'text': value}


class MirrorType(MondayComplexType):
    
    def __init__(self, _type: MondayType, id: str = None, title: str = None, *args, **kwargs):
        self._type = _type
        super().__init__(id=id, title=title, *args, **kwargs)

    def to_native(self, value, context):
        if not self._is_column_value(value):
            return value

        super().to_native(value, context)
        if self._type is NumberType:
            value.value = json.dumps(value.text)
            return self._get_monday_type().to_native(value, context)
        elif value.value == self.null_value:
            return self.default

    def to_primitive(self, value, context):
       self._get_monday_type().to_primitive(value, context)

    def _compare(self, value, other):
        return False

    def _get_monday_type(self):
        mirrored_type = getattr(importlib.import_module(self._type.__module__), self._type.__name__)
        try:
            id = self.metadata['id']
        except:
            id = None
        try:
            title = self.metadata['title']
        except:
            title = None
        return mirrored_type(id=id, title=title)


class NumberType(MondaySimpleType):

    primitive_type = str
    allow_casts = (str,)

    def validate_number(self, value):
        if isinstance(value, (int, float)):
            return
        elif isinstance(value, self.allow_casts):
            try:
                self.native_type(value)
                return
            except:
                pass
        raise ValidationError('Value is not a valid number type: ({}).'.format(value))

    def _convert(self, value, context):
        _, value, _ = value
        if value == self.null_value:
            return None
        if self._isint(value):
            self.native_type = int
            return int(value)
        if self._isfloat(value):
            self.native_type = float
            return float(value)

    def _export(self, value):
        if not value:
            return self.null_value
        return str(value)

    def _isfloat(self, value):
        """Is the value a float."""
        try:
            float(value)
        except ValueError:
            return False
        return True
  
    def _isint(self, value):
        """Is the value an int."""
        try:
            a = float(value)
            b = int(a)
        except ValueError:
            return False
        return a == b


class PeopleType(MondayComplexType):

    class PersonOrTeam():

        def __init__(self, id: str, kind: PeopleKind):
            self.id = id
            self.kind = kind

        
        def __repr__(self):
            return str({
                'id': self.id,
                'kind': self.kind})

    class Person(PersonOrTeam):

        def __init__(self, id: str):
            super().__init__(id, PeopleKind.person)

    class Team(PersonOrTeam):

        def __init__(self, id: str):
            super().__init__(id, PeopleKind.team)

    native_type = list
    primitive_type = dict

    def to_native(self, value, context):
        result = []
        if not self._is_column_value(value):
            return value
        value = super(PeopleType, self).to_native(value, context=context)
        # Custom rules for max people allowed setting.
        try:
            max_people_allowed = int(self.metadata['max_people_allowed'])
        except:
            max_people_allowed = 0
        self.metadata['max_people_allowed'] = max_people_allowed
        if value == self.null_value:
            return result

        for v in value['personsAndTeams']:
            kind = PeopleKind[v['kind']]
            result.append(self.PersonOrTeam(v['id'], kind))
        if max_people_allowed == 1:
            return result[0]
        return result

    def to_primitive(self, value, context = None):
        if not value:
            return self.null_value
        if type(value) is not list:
            value = [value]
        return {'personsAndTeams': [{'id': v.id, 'kind': v.kind.name} for v in value]}

    def validate_people(self, value, context):
        max_people_allowed = self.metadata['max_people_allowed']
        if max_people_allowed == 1 and type(value) != list:
            value = [value]
        if type(value) != list:
            raise ValidationError('Value is not a valid list type: ({}).'.format(value))
        if max_people_allowed > 0 and len(value) > max_people_allowed:
            raise ValidationError('Value exceeds the maximum number of allowed people: ({}).'.format(len(value)))
        for v in value:
            if not self._is_person_or_team(v):
                raise ValidationError('Value contains a record with an invalid type: ({})'.format(v.__class__.__name__))

    def _is_person_or_team(self, value):
        return isinstance(value, self.PersonOrTeam) or issubclass(type(value), self.PersonOrTeam)


class PhoneType(MondayComplexType):

    class Phone(ComplexTypeValue):

        def __init__(self, phone: str = None, country: str = None):
            self.phone = phone
            self.country = country

        def __repr__(self):
            return str({
                'phone': self.phone,
                'countryShortName': self.country})

    native_type = Phone
    primitive_type = dict

    def validate_phone(self, value):
        country = countries.get(alpha_2=value.country)
        if not country:
            raise ValidationError('Invalid country code: "{}".'.format(value.country))

    def _convert(self, value: tuple):
        _, value, _ = value
        if value == self.null_value:
            return self.native_type()
        return self.native_type(
            value['phone'],
            value['countryShortName'])

    def _export(self, value):
        if value.phone and value.country:
            return { 'phone': self.phone, 'countryShortName': self.country }
        return { 'phone': '', 'countryShortName': '' }


class StatusType(MondayComplexType):

    native_type = str
    primitive_type = dict

    def __init__(self, id: str = None, title: str = None, data_mapping: dict = None, *args, **kwargs):
        if data_mapping:
            self.native_type = data_mapping.values()[0].__class__
        self._data_mapping = data_mapping
        
        super(StatusType, self).__init__(id=id, title=title, *args, **kwargs)

    def to_native(self, value, context = None):
        if not self._is_column_value(value):
            return value
        super(StatusType, self).to_native(value, context)
        if not self._data_mapping:
            return value.text
        try:
            return self._data_mapping[value.text]
        except:
            return None

    def to_primitive(self, value, context = None):
        if self._data_mapping:
            reverse = {v: k for k, v in self._data_mapping.items()}
            value = reverse[value]
        for k, v in self.metadata['labels'].items():
            if value == v:
                return {'index': int(k)}
        return self.original_value

    def validate_status(self, value):
        if self._data_mapping:
            reverse = {v: k for k, v in self._data_mapping.items()}
            value = reverse[value]
        if value not in self.metadata['labels'].values():
            raise ValidationError('Unable to find index for status label: ({}).'.format(value))


class SubitemsType(ItemLinkType):

    null_value = None

    def __init__(self, _type: MondayModel, id: str = None, title: str = None, *args, **kwargs):
        if not issubclass(_type, MondayModel):
            raise TypeError('The input class type is not a Monday Model: ({})'.format(_type.__name__))
        self.type = _type
        super(SubitemsType, self).__init__(id, title, *args, default=[], **kwargs)

    def _convert(self, value):
        item_ids = super()._convert(value)
        if not item_ids:
            return self.default

        items = client.get_items(ids=item_ids, get_column_values=True)
        module = importlib.import_module(self.type.__module__)
        return [getattr(module, self.type.__name__)(item) for item in items]

    def validate_subitems(self, value):
        return # Nothing to validate here...

    def _compare(self, value, other):
        return False # Nothing to compare here...


class TextType(MondaySimpleType):

    native_type = str
    primitive_type = str
    allow_casts = (int, float, bytes)

    def to_native(self, value, context = None):
        if not self._is_column_value(value):
            return value
        return super(TextType, self).to_native(value, context)

    def to_primitive(self, value, context = None):
        if not value:
            return ''
        return value

    def validate_text(self, value):
        if type(value) is not str:
            raise ValidationError('Value is not a valid text type: ({}).'.format(value))



class TimelineType(MondayComplexType):

    class Timeline(ComplexTypeValue):

        def __init__(self, from_date = None, to_date = None):
            self.from_date = from_date
            self.to_date = to_date

        def __repr__(self):
            return str({
                'from': datetime.strftime(self.from_date, DATE_FORMAT),
                'to': datetime.strftime(self.to_date, DATE_FORMAT)
            })

    native_type = Timeline
    primitive_type = dict

    def _convert(self, value, context):
        _, value, _ = value
        if value == self.null_value:
            return self.native_type()

        try:
            return self.native_type(
                datetime.strptime(value['from'], DATE_FORMAT),
                datetime.strptime(value['to'], DATE_FORMAT))
        except:
            raise ConversionError(message='Invalid data for timeline type: ({}).'.format(value))

    def to_primitive(self, value, context = None):
        if not value:
            return self.null_value
        return {
            'from': datetime.strftime(value.from_date, DATE_FORMAT),
            'to': datetime.strftime(value.to_date, DATE_FORMAT)
        }

    def validate_timeline(self, value):
        if type(value) is not self.native_type:
            raise ValidationError('Value is not a valid timeline type: ({}).'.format(value))
        if value.from_date > value.to_date:
            raise ValidationError('Start date cannot be after end date.')

    
class WeekType(MondayComplexType):

    class Week(ComplexTypeValue):

        def __init__(self, start = None, end = None):
            self._start = start
            self._end = end
            self._calculate_dates(start)

        @property
        def start(self):
            return self._start

        @start.setter
        def start(self, value):
            self._calculate_dates(value)

        @property
        def end(self):
            return self._end

        @end.setter
        def end(self, value):
            return self._calculate_dates(value)

        @property
        def week_number(self):
            return self._week_number

        def _calculate_dates(self, value):
            if not value:
                return value   
            self._start = value - timedelta(days=value.weekday())
            self._end = self._start + timedelta(days=6)
            self._week_number = self._start.isocalendar()[1]

        def __repr__(self):
            return str({
                'startDate': self._start,
                'endDate': self._end
            })

    native_type = Week
    primitive_type = dict

    def to_native(self, value, context):
        if isinstance(value, self.native_type):
            return value
        if type(value) is dict:
            return self.native_type(value['start'], value['end'])
        value = super().to_native(value, context=context)
        try:
            week_value = value['week']
            if week_value == '':
                return self.native_type()
            return self.native_type(datetime.strptime(
                week_value['startDate'], DATE_FORMAT), 
                datetime.strptime(week_value['startDate'], DATE_FORMAT))
        except:
            return None

    def to_primitive(self, value, context = None):
        if not value:
            return self.null_value
        
        return { 
            'week': {
                'startDate': datetime.strftime(value.start, DATE_FORMAT),
                'endDate': datetime.strftime(value.end, DATE_FORMAT)
            }
        }

    def validate_week(self, value):
        if type(value) is not self.native_type:
            raise ValidationError('Value is not a valid week type: ({}).'.format(value))
        if not value.start:
            raise ValidationError('Value is mssing a start date: ({}).'.format(value))
        if not value.end:
            raise ValidationError('Value is mssing an end date: ({}).'.format(value))
            
    def value_changed(self, value):
        if self._null_value_change(value):
            return True
        orig_week = self.original_value['week']
        new_week = value['week']
        if orig_week == '' and new_week != orig_week:
            return True
        for k in new_week.keys():
            if new_week[k] != orig_week[k]:
                return True
        return False