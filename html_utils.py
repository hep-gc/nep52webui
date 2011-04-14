# Utility method to wrap some html content into a proper
# html page.
def wrap(body_content):
    html = ''
    html += '<html><head>'
    html += '<script src="/js/sorttable.js"></script>'
    html += """
    <link type="text/css" rel="stylesheet" media="all" href="/modules/node/node.css?r" />
<link type="text/css" rel="stylesheet" media="all" href="/modules/system/defaults.css?r" />
<link type="text/css" rel="stylesheet" media="all" href="/modules/system/system.css?r" />
<link type="text/css" rel="stylesheet" media="all" href="/modules/system/system-menus.css?r" />
<link type="text/css" rel="stylesheet" media="all" href="/modules/user/user.css?r" />

<link type="text/css" rel="stylesheet" media="all" href="/sites/default/files/color/garland-a6a3c2c3/style.css?r" />
<link type="text/css" rel="stylesheet" media="print" href="/themes/garland/print.css?r" />
"""
    html += '</head>'
    html += '<body><div class="content clear-block">%s</div></body>' % (body_content)
    html += '</html>'
    return html

def message(msg):
    return wrap('<p>%s</p>' % (msg))

def exception_page(exception):
    return wrap("%s" % exception)

def yes_no_page(prompt, yes_action, no_action):
    content = ''
    content += '<p>%s</p>' % prompt
    content += '<a href="%s">Yes</a>' % (yes_action)
    content += '&nbsp;<a href="%s">No</a>' % (no_action)
    return wrap(content)
