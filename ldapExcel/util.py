import collections

def unicode_to_str_dict(data):
    '''
    Helper function to transform a unicode composed dictionary to a string composed dictionary

    :param data: dictionary to be transformed
    :return: transformed dictonary
    '''

    if isinstance(data, str) or isinstance(data, unicode):
        clean_data = filter(lambda x: 32 <= ord(x) < 127, data)
        return str(clean_data)

    elif isinstance(data, collections.Mapping):
        return dict(map(unicode_to_str_dict, iter(data.items())))

    elif isinstance(data, collections.Iterable):
        return type(data)(map(unicode_to_str_dict, data))

    else:
        return data