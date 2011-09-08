from decimal import *
import html_utils
import cherrypy

class VmImageCreationForm():
    def __init__(self, available_images):
        self.available_images = available_images

    def get_form_html(self):
        html = """
<h3>Image metadata:</h3>
<p>Fields marked with a '<sup>*</sup>' are mandatory.
<form action="/webui/create_image" method="post" enctype="multipart/form-data">
  <table>
    <thead></thead>
    <tbody>
      <tr>
	<th align="right">Image name:</th><td><input type="text" name="image_name" size="40"/>&nbsp;<sup>*</sup></td>
      </tr>
       <tr>
	<th align="right">Description:</th><td><input type="text" name="image_description" size="40"/></td>
      </tr>
      <tr>
        <th align="right">Image source:</th><td><input type="radio" name="image_source" value="from_uploaded_file" checked/>Upload:&nbsp;<input type="file" name="image_file" /><br><input type="radio" name="image_source" value="from_existing_image"/>Clone:&nbsp;<select name="source_image">"""

        if self.available_images != None:
            for image in self.available_images:
                image_stripped = ('%s/%s') % (image.split('/')[-2], image.split('/')[-1])
                html += '<option value="%s">%s</option>' % (image_stripped, image_stripped)

        html += """
      </select><br>
      <input type="radio" name="image_source" value="no_image"/>No image data (metadata only)</td>
      </tr>
      <tr>
        <th align="right">Give unauthenticated access to this image?<br><small>Note: This will make it accessible via http.</small></th><td><input type="radio" name="unauthenticated_access" value="True"/>Yes<br><input type="radio" name="unauthenticated_access" value="False" checked/>No</td>
      </tr>
   </tbody>
  </table>
  <INPUT type="submit" value="Submit">&nbsp;<input type="reset" value="Reset">
</form>
"""
        return html

class VmImageEditForm():
    def to_html_value(self, value):
        if value == None:
            return ''
        else:
            return value

    def get_form_html(self, repoman_server, image, users, groups):
        html = ''
        html += '<form action="/webui/edit_image" method="post" enctype="multipart/form-data">'
        html += '<input type="hidden" name="orig_name" value="%s">' % (image['name'])
        html += '<input type="hidden" name="orig_owner" value="%s">' % (image['owner_user_name'])
        html += '<input type="hidden" name="repoman_server" value="%s">' % (repoman_server)
        html += '<table border="1">'

        html += '<tr>'
        html += '<td>name:</td><td><input type="text" name="name" value="%s"></td>' % (self.to_html_value(image['name']))
        html += '</tr>'

        html += '<tr>'
        html += '<td>description:</td><td><input type="text" name="description" value="%s"></td>' % (self.to_html_value(image['description']))
        html += '</tr>'

        html += '<tr>'
        html += '<td>Image file:</td><td>'
        if image['raw_file_uploaded'] == False:
            html += 'No image uploaded yet.'
        else:
            getcontext().prec = 4
            html += '%s<br><small>(%s MBytes)</small>' % (image['file_url'], Decimal(image['size'])/Decimal(1048576.0))

        html += '<br><input type="file" name="image_file" /><br><small>Select a file here if you want to upload a new image.<br>Note that this will overwrite the previous image, if any.</small></td>'
        html += '</tr>'

        html += '<tr>'
        html += '<td>hypervisor:</td><td><input type="text" name="hypervisor" value="%s"></td>' % (self.to_html_value(image['hypervisor']))
        html += '</tr>'

        selected_items = {}
        selected_items['x86'] = ''
        selected_items['x86_64'] = ''
        selected_items[image['os_arch']] = 'selected'
        html += '<tr>'
        html += '<td>OS architecture:</td><td><select name="os_arch"><option value="x86" %s>x86</option><option value="x86_64" %s>x86_64</option></select></td>' % (selected_items['x86'], selected_items['x86_64'])
        html += '</tr>'

        html += '<tr>'
        html += '<td>OS type:</td><td><input type="text" name="os_type" value="%s"></td>' % (self.to_html_value(image['os_type']))
        html += '</tr>'

        html += '<tr>'
        html += '<td>OS variant:</td><td><input type="text" name="os_variant" value="%s"></td>' % (self.to_html_value(image['os_variant']))
        html += '</tr>'

        checked_items = {}
        checked_items['True'] = ''
        checked_items['False'] = ''
        if image['read_only']:
            checked_items['True'] = 'checked'
        else:
            checked_items['False'] = 'checked'
        html += '<tr>'
        html += '<td>Permissions:</td><td><input type="radio" name="read_only" value="True" %s>read only<br><input type="radio" name="read_only" value="False" %s>read and write</td>' % (checked_items['True'], checked_items['False'])
        html += '</tr>'

        html += '<tr>'
        html += '<td>Share with users:</td><td>'
        for user_l in users:
            user = user_l.split('/')[-1]
            checked = ''
            if user_l in image['shared_with']['users']:
                checked = 'checked'
            html += '<input type="checkbox" name="shared_with_users" value="%s" %s>%s<br>' % (user_l, checked, user)
        html += '</td>'
        html += '</tr>'

        html += '<tr>'
        html += '<td>Share with groups:</td><td>'
        for group_l in groups:
            group = group_l.split('/')[-1]
            checked = ''
            if group_l in image['shared_with']['groups']:
                checked = 'checked'
            html += '<input type="checkbox" name="shared_with_groups" value="%s" %s>%s<br>' % (group_l, checked, group)
        html += '</td>'
        html += '</tr>'


        checked_items = {}
        checked_items['yes'] = ''
        checked_items['no'] = ''
        if image['unauthenticated_access']:
            checked_items['yes'] = 'checked'
        else:
            checked_items['no'] = 'checked'
        html += '<tr>'
        html += '<td>Unauthenticated access:</td><td><input type="radio" name="unauthenticated_access" value="yes" %s>yes<br><input type="radio" name="unauthenticated_access" value="no" %s>no</td>' % (checked_items['yes'], checked_items['no'])
        html += '</tr>'

        html += '</table>'
        html +='<INPUT type="submit" value="Apply">&nbsp;<input type="reset" value="Reset">'
        html += '</form>'
        return html


class VmBootForm():
    def __init__(self, image_metadata):
        self.image_metadata = image_metadata
        
    def get_html(self):
        if self.image_metadata['os_arch'] == None:
            self.image_metadata['os_arch'] = 'x86';

        html = ''

        html += """
<html><head></head>
<body>
<form action="/webui/boot_vm" method="post">
  <table>
    <thead></thead>
    <tbody>"""

        html += """
      <tr>
	<th align="right">Image name:</th><td><input type="text" name="image_name" size="40" value="%s"/></td>
      </tr>""" % (self.image_metadata['name'])

        html += """
      <tr>
	<th align="right">Image location:</th><td><input type="text" name="image_location" size="40" value="%s"/></td>
      </tr>""" % (self.image_metadata['http_file_url'])

        html += """
      <tr>
	<th align="right">Architecture:</th><td><input type="text" name="arch" size="40" value="%s"/></td>
      </tr>""" % (self.image_metadata['os_arch'])

        html += """
      <tr>
	<th align="right">Cloud:</th><td>
          <select name="cloud">
            <option value="alto.cloud.nrc.ca">alto.cloud.nrc.ca</option>
          </select></td>
      </tr>

      <tr>
	<th align="right">RAM (MB):</th><td>
          <select name="ram">
            <option value="512">512</option>
            <option value="1024">1024</option>
            <option value="2048">2048</option>
            <option value="4096">4096</option>
          </select></td>
      </tr>"""

        # default value: minimum 5GB of space or current image size
        blank_space_MB = max((1024**3) * 5, self.image_metadata['size'])/(1024**2)
        html += """
      <tr>
	<th align="right">Blank space:</th><td><input type="text" name="blank_space_MB" size="10" value="%s"/>&nbsp;MBytes</td>
      </tr>""" % (blank_space_MB)

        html += """
      <tr>
	<th align="right">Network:</th><td>
          <select name="network">
            <!--
            <option value="private">private</option>
            <option value="public">public</option>
            <option value="batch">batch</option>
            -->
            <option value="interactive">interactive</option>
          </select></td>
      </tr>

      <tr>
	<th align="right"># CPUs:</th><td>
          <select name="cpus">
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="4">4</option>
         </select></td>
      </tr>
    </tbody>
  </table>
  <INPUT type="submit" value="Boot">&nbsp;<input type="reset" value="Reset">
</form>
</body>
</html>""" 
        return html
