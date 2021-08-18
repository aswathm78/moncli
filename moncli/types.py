import json, pytz, importlib, re
import pytz
from datetime import datetime, timedelta
from enum import Enum

from pycountry import countries
from schematics.exceptions import ConversionError, ValidationError
from schematics.types import BaseType

from . import client
from .entities import BaseCollection, ColumnValue
from .enums import PeopleKind
from .models import MondayModel

DATE_FORMAT = '%Y-%m-%d'
TIME_FORMAT = '%H:%M:%S'
ZULU_FORMAT = '{}T{}.%fZ'.format(DATE_FORMAT, TIME_FORMAT)


class MondayType(BaseType):

    null_value = None
    allow_casts = ()
    native_default = None

    def __init__(self, id: str = None, title: str = None, *args, **kwargs):
        self.original_value = None
        metadata = {}

        if not id and not title:
            raise TypeError('"id" or "title" parameter is required.')
        if id:
            metadata['id'] = id
        if title:
            metadata['title'] = title

        # Handle defaults
        default = kwargs.pop('default', None)
        if not default:
            default = self.native_default

        super(MondayType, self).__init__(*args, default=default, metadata=metadata, **kwargs)

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

        if not isinstance(value, ColumnValue):
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
            changed_at = value.pop('changed_at', None)
            if changed_at:
                self.metadata['changed_at'] = datetime.strptime(changed_at, ZULU_FORMAT)
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
    native_default = False

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

        def __init__(self, name: str = None, code: str = None):
            self.name = name
            self.code = code

    native_type = Country
    primitive_type = dict
    native_default = native_type()

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
    native_default = []

    def __init__(self, id: str = None, title: str = None, data_mapping: dict = None, *args, **kwargs):
        if data_mapping:
            self._data_mapping = data_mapping
            self.choices = data_mapping.values()
        super(DropdownType, self).__init__(id=id, title=title, *args, **kwargs)

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

        def __init__(self, email: str = None, text: str = None):
            self.email = email
            if not text:
                text = email
            self.text = text

    native_type = Email
    primitive_type = dict
    native_default = native_type()

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
    native_default = []

    def __init__(self, id: str = None, title: str = None, multiple_values: bool = True, *args, **kwargs):
        if not multiple_values:
            self.native_type = str
            self.native_default = None
        super().__init__(id=id, title=title, *args, **kwargs)
        self.metadata['allowMultipleItems'] = multiple_values 

    @property
    def multiple_values(self):
        try:
            return self.metadata['allowMultipleItems']
        except: 
            return True

    def validate_itemlink(self, value):
        if not self.multiple_values:
            if value != None and isinstance(value, list):
                raise ValidationError('Multiple items for this item link property are not supported.')
        else:
            if value and not isinstance(value, (list, BaseCollection)):
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

    @property
    def instance(self):
        _class = getattr(importlib.import_module(self._type.__module__), self._type.__name__)
        return _class(self.metadata.get('id', None), self.metadata.get('title', None))

    def _convert(self, value):
        return getattr(self.instance, '_convert')(value)

    def _export(self, value):
        return None

    def _compare(self, value, other):
        return False


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

    def _convert(self, value):
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

    class PersonOrTeam(ComplexTypeValue):

        def __init__(self, id: str = None, kind: PeopleKind = None):
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

    class PeopleCollection():
        def __init__(self, column_values: list = []):
            self._values = []
            for value in column_values:
                if not isinstance(value, PeopleType.PersonOrTeam):
                    raise TypeError(value)
                self._values.append(value)

        def __len__(self):
            return len(self._values)

        def __getitem__(self, index):
            try:
                i = self._get_index(index)
                return self._values[i]
            except:
                raise KeyError(index)

        def __setitem__(self, index, value):
            try:
                i = self._get_index(index)
                self._values[i] = value
            except:
                raise KeyError(index)

        def __iter__(self):
            for value in self._values:
                yield value

        def __repr__(self):
            return str([value.to_primitive() for value in self._values])

        def insert(self, index, value):
            i = self._get_index(index)
            self._values.insert(i, value)

        def append(self, value):
            self.insert(len(self._values), value)

        def _get_index(self, index):
            if isinstance(index, int):
                return index
            
            if not isinstance(index, str):
                raise TypeError(index)

            try:
                [people for people in self._values if people.id == index][0]
            except: 
                raise KeyError(index)
    
    native_type = PeopleCollection
    primitive_type = dict
    allow_casts = (list, dict)
    native_default = native_type()

    def __init__(self, id: str = None, title: str = None, max_allowed: int = 0, *args, **kwargs):
        super().__init__(id, title, *args, **kwargs)
        self.metadata['max_people_allowed'] = max_allowed        
        self._set_native_type()

    @property
    def max_allowed(self):
        try:
            return int(self.metadata['max_people_allowed'])
        except:
            return 0

    def validate_people(self, value):
        if self.max_allowed == 1 and not isinstance(value, self.PeopleCollection):
            value = self.PeopleCollection([value])
        if not isinstance(value, self.PeopleCollection):
            raise ValidationError('Value is not a valid list type: ({}).'.format(value))
        if self.max_allowed > 0 and len(value) > self.max_allowed:
            raise ValidationError('Value exceeds the maximum number of allowed people: ({}).'.format(len(value)))
        for v in value:
            if not self._is_person_or_team(v):
                raise ValidationError('Value contains a record with an invalid type: ({})'.format(v.__class__.__name__))

    def _cast(self, value):
        if self.max_allowed == 1:
            if isinstance(value, list):
                return ConversionError('Cannot create single Person or Team record from list data. ({})'.format(value))
            try:
                return self.native_type(value['id'], value['kind'])
            except:
                return ConversionError('Cannot create single Person or Team record from input data. ({})'.format(value))

        if isinstance(value, dict):
            return ConversionError('Cannot create Person or Team record list from dict data. ({})'.format(value))
        try:
            return self.native_type([self.PersonOrTeam(value['id'], value['kind']) for value in value])
        except:
            return ConversionError('Cannot create Person or Team record list from input data. ({})'.format(value))

    def _convert(self, value):
        self._set_native_type()
        _, value, _ = value
        if value == self.null_value:
            return self.native_type()        

        people = []
        for v in value['personsAndTeams']:
            id = v['id']
            kind = PeopleKind[v['kind']]
            people.append(self.PersonOrTeam(id, kind))  
        if self.max_allowed == 1:
            return people[0]
        return self.native_type(people)

    def _export(self, value):
        if not isinstance(value, self.PeopleCollection):
            if value == self.native_default:
                return self.null_value
            value = self.PeopleCollection([value])
        persons_and_teams = [{'id': v.id, 'kind': v.kind.name} for v in value if value != self.PersonOrTeam()]
        if not persons_and_teams:
            return self.null_value
        return {'personsAndTeams': persons_and_teams}

    def _set_native_type(self):
        if self.max_allowed == 1:
            self.native_type = self.PersonOrTeam
            self.native_default = self.native_type()

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
    native_default = native_type()

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
            values = list(data_mapping.values())
            self.native_type = values[0].__class__
            self.choices = values
        self._data_mapping = data_mapping
        
        super(StatusType, self).__init__(id=id, title=title, *args, **kwargs)

    def validate_status(self, value):
        if self._data_mapping:
            reverse = {v: k for k, v in self._data_mapping.items()}
            value = reverse[value]
        if value not in self.metadata['labels'].values():
            raise ValidationError('Unable to find index for status label: ({}).'.format(value))

    def _convert(self, value):
        text, _, _ = value
        if not self._data_mapping:
            return text
        try:
            return self._data_mapping[text]
        except:
            return None

    def _export(self, value):
        if self._data_mapping:
            reverse = {v: k for k, v in self._data_mapping.items()}
            value = reverse[value]
        for k, v in self.metadata['labels'].items():
            if value == v:
                return {'index': int(k)}


class SubitemsType(ItemLinkType):

    null_value = None
    native_type = list

    def __init__(self, _type: MondayModel, id: str = None, title: str = None, as_collection: type = None, *args, **kwargs):
        if not issubclass(_type, MondayModel):
            raise TypeError('The input class type is not a Monday Model: ({})'.format(_type.__name__))
        if as_collection: 
            if not issubclass(as_collection, BaseCollection):
                raise TypeError('The input collection type is not a BaseCollection type: ({}).'.format(as_collection.__name__))
            self.native_type = as_collection
        self.type = _type
        super(SubitemsType, self).__init__(id, title, *args, default=[], **kwargs)

    def validate_subitems(self, value):
        return # Nothing to validate here...

    def _convert(self, value):
        item_ids = super()._convert(value)
        if not item_ids:
            return self.native_type()

        items = client.get_items(ids=item_ids, get_column_values=True)
        module = importlib.import_module(self.type.__module__)
        return self.native_type([getattr(module, self.type.__name__)(item) for item in items])

    def _compare(self, value, other):
        return False # Nothing to compare here...


class TextType(MondaySimpleType):

    native_type = str
    primitive_type = str
    allow_casts = (int, float, bytes)

    def validate_text(self, value):
        if isinstance(value, str):
            return
        if isinstance(value, self.allow_casts):
            return 
        raise ValidationError('Value is not a valid text type: ({}).'.format(value))

    def _convert(self, value):
        _, value, _ = value
        if value == self.null_value:
            return None
        return value


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
    native_default = native_type()
    allow_casts = (dict,)

    def validate_timeline(self, value):
        if type(value) is not self.native_type:
            raise ValidationError('Value is not a valid timeline type: ({}).'.format(value))
        if value == self.native_default:
            return
        if value.from_date > value.to_date:
            raise ValidationError('Start date cannot be after end date.')

    def _cast(self, value):
        if not value:
            return self.native_default
        try:
            return self.native_type(
                value['from'],
                value['to'])
        except:
            raise ConversionError(message='Invalid data for timeline type: ({}).'.format(value))

    def _convert(self, value):
        _, value, _ = value
        if value == self.null_value:
            return self.native_type()

        try:
            return self.native_type(
                datetime.strptime(value['from'], DATE_FORMAT),
                datetime.strptime(value['to'], DATE_FORMAT))
        except:
            raise ConversionError(message='Invalid data for timeline type: ({}).'.format(value))

    def _export(self, value):
        if value == self.native_default:
            return self.null_value
        return {
            'from': datetime.strftime(value.from_date, DATE_FORMAT),
            'to': datetime.strftime(value.to_date, DATE_FORMAT)
        }


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
    allow_casts = (dict,)

    def validate_week(self, value):
        if isinstance(value, self.native_type):
            return
        raise ValidationError('Value is not a valid week type: ({}).'.format(value))

    def _cast(self, value):
        try:
            return self.native_type(
                value['start'],
                value['end'])
        except:
            raise ConversionError('Unable to cast input dict as Week type. ({}).'.format(value))

    def _convert(self, value):
        _, value, _ = value
        try:
            week_value = value['week']
            if week_value == '':
                return self.native_type()
            return self.native_type(datetime.strptime(
                week_value['startDate'], DATE_FORMAT), 
                datetime.strptime(week_value['startDate'], DATE_FORMAT))
        except:
            return self.native_type()

    def _export(self, value):
        if not value.start or not value.end:
            return self.null_value
        return { 
            'week': {
                'startDate': datetime.strftime(value.start, DATE_FORMAT),
                'endDate': datetime.strftime(value.end, DATE_FORMAT)
            }
        }

    