import re

class CondorCommandParsingError(Exception):
    pass

# The following is based on some code written by Patrick Armstrong.
class CondorQOutputParser():

    def condor_q_to_classad_list(self, condor_q_output):
        """
        _condor_q_to_classad_list - Converts the output of condor_q
                to a list of classads

                returns [] if there are no jobs
        """

        def _attribute_from_requirements(requirements, attribute):
            regex = "%s\s=\?=\s\"(?P<value>.+?)\"" % attribute
            match = re.search(regex, requirements)
            if match:
                return match.group("value")
            else:
                return ""

        def _attribute_from_list(classad, attribute):
            try:
                attr_list = classad[attribute]
                try:
                    attr_dict = _attr_list_to_dict(attr_list)
                    classad[attribute] = attr_dict
                except ValueError:
                    raise CondorCommandParsingError("Problem extracting %s attribute '%s'" % (attribute, attr_list))
            except:
                pass

        classads = []
        # The first three lines look like:
        # \n\n\t-- Submitter: hostname : <ip> : hostname
        # we can just strip these.
        condor_q_output = re.sub('\n\n.*?Submitter:.*?\n', "", condor_q_output, re.MULTILINE)

        # Each classad is seperated by '\n\n'
        raw_job_classads = condor_q_output.split("\n\n")
        # Empty condor pools give us an empty string in our list
        raw_job_classads = filter(lambda x: x != "", raw_job_classads)

        for raw_classad in raw_job_classads:
            classad = {}
            classad_lines = raw_classad.splitlines()
            for classad_line in classad_lines:
                classad_line = classad_line.strip()
                (classad_key, classad_value) = classad_line.split(" = ", 1)
                classad_value = classad_value.strip('"')
                classad[classad_key] = classad_value

            try:
                classad["VMType"] = _attribute_from_requirements(classad["Requirements"], "VMType")
            except:
                raise CondorCommandParsingError("Problem extracting VMType from Requirements")

            # VMAMI requires special fiddling
            _attribute_from_list(classad, "VMAMI")
            _attribute_from_list(classad, "VMInstanceType")

            classads.append(classad)
        return classads


def _attr_list_to_dict(attr_list):
    """
    _attr_list_to_dict -- parse a string like: host:ami, ..., host:ami into a
    dictionary of the form:
    {
        host: ami
        host: ami
    }

    if the string is in the form "ami" then parse to format
    {
        default: ami
    }

    raises ValueError if list can't be parsed
    """

    attr_dict = {}
    for host_attr in attr_list.split(","):
        host_attr = host_attr.split(":")
        if len(host_attr) == 1:
            attr_dict["default"] = host_attr[0].strip()
        elif len(host_attr) == 2:
            attr_dict[host_attr[0].strip()] = host_attr[1].strip()
        else:
            raise ValueError("Can't split '%s' into suitable host attribute pair" % host_attr)

    return attr_dict
