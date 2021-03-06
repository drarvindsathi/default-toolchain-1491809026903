import requests
import json
import time
import datetime
import constants
from operator import itemgetter

schemaFileLocation='schema.json'
headers=''

def post (url, data):
    response = requests.post(url, data=data, headers=headers)
    if (response.status_code == 401) or (response.status_code == 403):
        print 'Expired token. Requesting a new token...'
        updateToken()
        response = requests.post(url, data=data, headers=headers)
    return response
    
def get (url):
    response = requests.get(url, headers=headers)
    if (response.status_code == 401) or (response.status_code == 403):
        print 'Expired token. Requesting a new token...'
        updateToken()
        response = requests.get(url, headers=headers)
    return response

def getAllPrints():
    print 'Getting the prints...'
    gremlin = {
        "gremlin": "def gt = graph.traversal();" + 
                   "gt.V().has(\"type\", \"print\");"
        }
    response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/gremlin', json.dumps(gremlin))
    prints = {}
    if (response.status_code == 200):
        prints = json.loads(response.content)['result']['data']
        print 'Successfully got the prints'
    else:
        raise ValueError('An error occurred while getting the prints: %s. %s' %
                         (response.status_code, response.content))
    return prints

def getRecommendedPrints(username):
    # Code based on Apache TinkerPop recipe for recommendations:
    # http://tinkerpop.apache.org/docs/current/recipes/#recommendation
    if not username:
        username = ""
 
    prints = []
    
    # Search for recommended prints for the given user based on
    # what prints other users who have also purchased one or more
    # of the same prints have purchased. Results will be sorted
    # so the top 3 most popular prints among the users will be 
    # displayed first    
    gremlin = {
        # create a new traversal
        "gremlin": "def gt = graph.traversal();" + 
            # create a function that handles storing both the image name and image path in the results
            "java.util.function.Function byNameImgPath = { Vertex v -> \"\" + v.value(\"name\") + \":\" + v.value(\"imgPath\") };" +
            # search for the signed-in user and name them 'buyer'
            "gt.V().hasLabel(\"user\").has(\"username\", \"" + username + "\").as(\"buyer\")" +
            # go out from the buyer node to find all of the prints the buyer has purchased
            # and name them 'bought'
            ".out(\"buys\").aggregate(\"bought\")" +
            # go in to find all users (except for our 'buyer') who have purchased at 
            # least one of these prints. remove duplicates as we only need to find 
            # each buyer once.
            ".in(\"buys\").where(neq(\"buyer\")).dedup()" + 
            # go out to find the prints these users have purchased. exclude the prints
            # that the 'buyer' has already 'bought'
            ".out(\"buys\").where(without(\"bought\"))" +
            # group and sort to find the top 3 recommendations
            ".groupCount().by(byNameImgPath).order(local).by(valueDecr).limit(local, 3);"
        }

    response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/gremlin', json.dumps(gremlin))

    if (response.status_code == 200):  
        results = json.loads(response.content)['result']['data']
        if len(results) > 0:
            results = results[0]
            # We lose the sorting from the query results when we do json.loads.
            # Sort the results in descending order by value.
            results = sorted(results.items(), key=itemgetter(1), reverse=True)
            
            for p in results:  
                newPrint = {}
                newPrint['name'] = p[0].split(':', 1)[0]
                newPrint['imgPath'] = p[0].split(':', 1)[1]
                prints.append(newPrint)
                print 'Found personalized recommendation for user with username %s: %s' % (username, newPrint['name'])
                
    if len(prints) >= 3:
        return prints
    
    print 'Going to search for generic print recommendations'
    
    # Search for the most-purchased prints 
    gremlin = {
        # create a new traversal
        "gremlin": "def gt = graph.traversal();" + 
            # create a function that handles storing both the image name and image path in the results
            "java.util.function.Function byNameImgPath = { Vertex v -> \"\" + v.value(\"name\") + \":\" + v.value(\"imgPath\") };" +
            # search for all of the users
            "gt.V().has(\"type\",\"user\")" +
            # go out from the user nodes to find all of the prints that have been bought
            ".out(\"buys\")" + 
            # group and sort to find the most purchased prints
            # limiting to 3 in case of duplicates from the personalized recommendations
            ".groupCount().by(byNameImgPath).order(local).by(valueDecr).limit(local, 3);"
        }
    
    response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/gremlin', json.dumps(gremlin))

    if (response.status_code == 200):  
        results = json.loads(response.content)['result']['data']
        if len(results) > 0:
            results = results[0]
            # We lose the sorting from the query results when we do json.loads.
            # Sort the results in descending order by value.
            results = sorted(results.items(), key=itemgetter(1), reverse=True)
            
            i = 0
            while ( len(prints) < 3 and i < len(results) ):
                p = results[i]  
                newPrint = {}
                name = p[0].split(':', 1)[0]
                if isDuplicateRecommendation(prints, name):
                    print 'Found duplicate recommendation (%s). Will search for another recommendation.' % name
                    i += 1
                    continue
                newPrint['name'] = name
                newPrint['imgPath'] = p[0].split(':', 1)[1]
                prints.append(newPrint)
                print 'Found most purchased print as recommendation: %s' % newPrint['name']
                i += 1
            return prints    
        
    raise ValueError('An error occurred while trying to generate print recommendations %s: %s.' % (response.status_code, response.content))

def isDuplicateRecommendation(recommendedPrints, nameOfNewRecommendation):
    for recommendation in recommendedPrints:
        if (nameOfNewRecommendation == recommendation['name']):
             return True
        else:
             return False

def insertSampleData():    
    print 'Inserting sample data...'
    
    try: 
        createUser('Jason', 'Schaefer', 'jason', 'jason@example.com')
    except ValueError as e:
        print e
    
    try:
        createUser('Joy', 'Haywood', 'joy', 'joy@example.com')
    except ValueError as e:
        print e
    
    try:
        createUser('Deanna', 'Howling', 'deanna', 'deanna@example.com')
    except ValueError as e:
        print e
    
    try:
        createUser('Dale', 'Haywood', 'dale', 'dale@example.com')
    except ValueError as e:
        print e
    
    createPrint('Alaska', 'Lauren loves this photo even though she wasn\'t present ' + 
                'when the photo was taken. Her husband took this photo on a guy\'s weekend in Alaska.',
                75.00, 'alaska.jpg')
    createPrint('Antarctica', 'Lauren\'s husband took this spectacular photo when they visited ' +
                'Antarctica in December of 2012. This is one of our hot sellers, so it rarely goes on sale. ',
                100.00, 'penguin.jpg')
    createPrint('Australia', 'Lauren loved her trip to Australia so much that she named her daughter Sydney. ',
                120.00, 'sydney.jpg')
    createPrint('Las Vegas', 'What happens in Vegas, stays in Vegas...unless you take a picture.',
                90.00, 'vegas.jpg')
    createPrint('Japan', 'Lauren and her husband babymooned in gorgeous Japan.',
                95.00, 'japan.jpg')
    createPrint('Israel', 'Lauren and her husband were able to tour Israel after Lauren spoke at IBM Business Connect in Tel Aviv in 2014.',
                80.00, 'israel.jpg')
    createPrint('Kenya', 'Jason and Lauren went on safari in Kenya after Lauren spent 4 weeks working in Nairobi as part of the IBM Corporate Service Corps.',
                120.00, 'kenya.jpg')
    
    buyPrint('jason', 'Alaska', "2016-10-15 13:13:17", 'Jason', 'Schaefer', '123 Sweet Lane', 'Apt #5', 'Valentine', 'NE', 69201, 'Paypass' )
    buyPrint('jason', 'Las Vegas', "2016-02-03 16:05:02", 'Jason', 'Schaefer', '123 Sweet Lane', 'Apt #5', 'Valentine', 'NE', 69201, 'Paypass' )
    buyPrint('jason', 'Australia', "2016-06-09 06:45:42", 'Chuck', 'Howling', '529 Green St', '', 'Omaha', 'NE', 68104, 'Credit card' )
    buyPrint('joy', 'Alaska', "2015-12-24 04:34:52", 'Joy', 'Haywood', '423 Purple St', '', 'Honolulu', 'HI', 96818, 'Credit card' )
    buyPrint('joy', 'Antarctica', "2015-12-29 16:25:02", 'Joy', 'Haywood', '423 Purple St', '', 'Honolulu', 'HI', 96818, 'Credit card' )
    buyPrint('joy', 'Las Vegas', "2016-04-22 14:48:30", 'Joy', 'Haywood', '423 Purple St', '', 'Honolulu', 'HI', 96818, 'Credit card' )
    buyPrint('joy', 'Japan', "2016-04-06 09:55:48", 'Joy', 'Haywood', '423 Purple St', '', 'Honolulu', 'HI', 96818, 'Credit card' )
    buyPrint('deanna', 'Alaska', "2016-01-17 08:46:20", 'Deanna', 'Howling', '2 Flamingo Lane', '', 'Chicago', 'IL', 60629, 'Credit card' )
    buyPrint('deanna', 'Antarctica', "2016-06-09 12:05:30", 'Chuck', 'Howling', '529 Green St', '', 'Omaha', 'NE', 68104, 'Credit card' )
    buyPrint('deanna', 'Las Vegas', "2016-10-20 13:50:00", 'Deanna', 'Howling', '2 Flamingo Lane', '', 'Chicago', 'IL', 60629, 'Paypass' )
    buyPrint('dale', 'Las Vegas', "2016-05-05 22:15:45", 'Dale', 'Haywood', '25 Takeflight Ave', '', 'Houston', 'TX', 77036, 'Paypass' )
    buyPrint('dale', 'Australia', "2016-05-06 10:15:25", 'Dale', 'Haywood', '25 Takeflight Ave', '', 'Houston', 'TX', 77036, 'Paypass' )
    buyPrint('dale', 'Japan', "2016-05-06 10:18:30", 'Dale', 'Haywood', '25 Takeflight Ave', '', 'Houston', 'TX', 77036, 'Paypass' )
    print 'Sample data successfully inserted'

def getUser(username):
    gremlin = {
        "gremlin": "def gt = graph.traversal();gt.V().hasLabel(\"user\").has(\"username\", \"" + username + "\");"
        }
    response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/gremlin', json.dumps(gremlin))
    if (response.status_code == 200):  
        results = json.loads(response.content)['result']['data'] 
        if len(results) > 0:
            user = results[0]
            print 'Found user with username %s.' % username
            return user

    raise ValueError('Unable to find user with username %s' % username)

# not currently letting usernames be updated
def updateUser(username, firstName, lastName, email):
    print 'update user: %s' % firstName
    gremlin = {
        "gremlin": "def gt = graph.traversal();" +
            "gt.V().hasLabel('user').has('username', '" + username + "')" +
            ".property('firstName', '" + firstName + "')" + 
            ".property('lastName', '" + lastName + "')" +
            ".property('email', '" + email + "');" 
        }
    response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/gremlin', json.dumps(gremlin))
    if (response.status_code == 200): 
        print 'Successfully updated user %s with the following values: %s %s %s' % (username, firstName, lastName, email)
        return True
    else:
        raise ValueError('An error occurred while trying to update user %s: %s %s.' % (username, response.status_code, response.content))
        return False
        
    
def doesUserExist(username):    
    print 'Getting user with username %s from the graph' % username
    gremlin = {
        "gremlin": "def gt = graph.traversal();" + 
                   "gt.V().hasLabel(\"user\").has(\"username\", \"" + username + "\");"
        }
    response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/gremlin', json.dumps(gremlin))
    if len(json.loads(response.content)['result']['data']) > 0 :
        return True
    return False

def getAllUsers():
    gremlin = {
        "gremlin": "def gt = graph.traversal();" + 
                   "gt.V().has(\"type\", \"user\");"
        }
    response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/gremlin', json.dumps(gremlin))
    if len(json.loads(response.content)['result']['data']) > 0 :
        return json.loads(response.content)['result']['data']
    return {}
    
def createUser(firstName, lastName, username, email):
    
    if doesUserExist(username):
        raise ValueError('The username \'%s\' is already taken. Get creative and try again.' % username)
        return
    
    # if the user does not already exist, create the user
    print 'Creating new user'
    gremlin = {
        "gremlin": "def gt = graph.traversal();" + 
                   "gt.addV(" +
                        "label, 'user'," +
                        "'firstName', '" + firstName + "'," + 
                        "'lastName', '" + lastName + "'," + 
                        "'username', '" + username + "'," + 
                        "'email', '" + email + "'," + 
                        "'type', 'user'" + 
                        ");" 
        }
    
    response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/gremlin', 
                             json.dumps(gremlin))
    if (response.status_code == 200):
        print 'User successfully created: %s' % username
    else:
        raise ValueError('User not created successfully: %s. %s. %s' %
                         (username, response.status_code, response.content))
        
def getPrintInfo(name):
    gremlin = {
        "gremlin": "def gt = graph.traversal();" + 
                    "gt.V().hasLabel('print').has('name', '" + name + "');"
    }
    response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/gremlin', json.dumps(gremlin))
    
    if (response.status_code == 200):  
        results = json.loads(response.content)['result']['data'] 
        if len(results) > 0:
            printInfo = results[0]
            print 'Found print with name %s.' % name
            return printInfo

    raise ValueError('Unable to find print with name %s' % name)

def createPrint(name, description, price, imgPath):
    
    # check if a print with the given name already exists
    try:
        getPrintInfo(name)
        print 'Print with name %s already exists. Print will not be created.' % name
        return
    except ValueError:
        print 'Print with name %s does not exist.  Will create new print...' % name
    
    gremlin = {
    "gremlin": "def gt = graph.traversal();" + 
               "gt.addV(" +
                    "label, 'print'," +
                    "'name', \"" + name + "\"," + 
                    "'description', \"" + description + "\"," + 
                    "'price', " + str(price) + "," + 
                    "'imgPath', '" + imgPath + "'," + 
                    "'type', 'print'" + 
                    ");" 
    }

    response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/gremlin', 
                             json.dumps(gremlin))
    if (response.status_code == 200):
        print 'Print successfully created: %s' % name
    else:
        raise ValueError('Print not created successfully: %s. %s. %s' %
                         (name, response.status_code, response.content))

def getAllOrders():
    gremlin = {
    "gremlin": "def gt = graph.traversal();" + 
               "gt.V().has('type', 'user').as('buyer')" + 
               ".out('buys')" + 
               ".inE('buys')" + 
               ".outV().where(eq('buyer'))" + 
               ".path()"
    }
    response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/gremlin', json.dumps(gremlin))
    
    if (response.status_code == 200):  
        results = json.loads(response.content)['result']['data'] 
        orders = []
        if len(results) > 0: 
            
            for result in results:
                order = {}
                for object in result['objects']:                   
                    if object['label']=='user':
                        order['username'] = object['properties']['username'][0]['value']
                        continue
                    if object['label']=='buys':
                        order['date'] = object['properties']['date']
                        order['firstName'] = object['properties']['firstName']
                        order['lastName'] = object['properties']['lastName']
                        order['address1'] = object['properties']['address1']
                        order['address2'] = object['properties']['address2']
                        order['city'] = object['properties']['city']
                        order['state'] = object['properties']['state']
                        order['zip'] = object['properties']['zip']
                        order['paymentMethod'] = object['properties']['paymentMethod']
                        continue
                    if object['label']=='print':
                        order['printName'] = object['properties']['name'][0]['value']
                        continue

                orders.append(order)
            
        return orders
        
def buyPrint(username, printName, date, firstName, lastName, address1, address2, city, state, zip, paymentMethod):
    
    gremlin = {
    "gremlin": "def gt = graph.traversal();" + 
               "def user = gt.V().hasLabel('user').has('username', '" + username + "').next();" + 
               "def print = gt.V().hasLabel('print').has('name', '" + printName + "').next();"
               "user.addEdge('buys', print," +
                    "'date', '" + str(date) + "'," + 
                    "'firstName', '" + firstName + "'," + 
                    "'lastName', '" + lastName + "'," + 
                    "'address1', '" + address1 + "'," + 
                    "'address2', '" + address2 + "'," + 
                    "'city', '" + city + "'," + 
                    "'state', '" + state + "'," + 
                    "'zip', " + str(zip) + "," + 
                    "'paymentMethod', '" + paymentMethod + "'," + 
                    "'type', 'buys'" + 
                    ");" 
    }
    
    response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/gremlin', json.dumps(gremlin))
    if (response.status_code == 200):
        print 'Print successfully bought: %s' % (json.dumps(gremlin))
    else:
        raise ValueError('Print not successfully bought: %s. %s: %s' %
                         (json.dumps(gremlin), response.status_code, response.content))
        
def updateToken():
    # get the gds-token
    response = requests.get(constants.API_URL + '/_session', 
                     auth=(constants.USERNAME, constants.PASSWORD))
    token = 'gds-token ' + json.loads(response.content)['gds-token']
    print token
    
    # set the headers for all of our requests to use the token
    global headers
    headers={'Authorization': token, 'Accept': 'application/json', 'Content-Type' : 'application/json'}
    print 'Updated headers: %s' % headers

def initializeGraph():
    updateToken()

    # if the graph is not already created, create it and create the schema and indexes
    print 'Checking to see if graph with id %s exists...' % (constants.GRAPH_ID)
    response = get(constants.API_URL + '/' + constants.GRAPH_ID)
    if response.status_code == 200:
        print 'Graph with id %s already exists' % (constants.GRAPH_ID)
    else:
        print 'Creating graph with id %s' % (constants.GRAPH_ID)
        response = post(constants.API_URL + '/_graphs/' + constants.GRAPH_ID, '')
        if (response.status_code == 201):
            print 'Graph with id %s successfully created'  % (constants.GRAPH_ID)
        else:
            raise ValueError('Graph with id %s not created successfully: %s. %s' %
                             (constants.GRAPH_ID, response.status_code, response.content))
        
        print 'Creating the schema and indexes for graph %s based on %s. This may take a minute or two...' % (constants.GRAPH_ID, schemaFileLocation)
        schema = open(schemaFileLocation, 'rb').read()
        response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/schema',
                             schema)
        if (response.status_code == 200):
            print 'Schema and indexes for graph %s successfully created based on %s' % (constants.GRAPH_ID, schemaFileLocation)
        else:
            raise ValueError('Schema and indexes for graph %s not created successfully: %s. %s' %
                             (constants.GRAPH_ID, response.status_code, response.content))

# Deletes 'Buys' edges, 'User' vertexes, and 'Print' vertexes
# Does not delete the graph itself            
def dropGraph():
    data = {
        "gremlin":  "def g = graph.traversal();" + 
                    "g.E().has('type', 'buys').drop();" + 
                    "g.V().has('type', within('print','user')).drop();" 
        }
    response = post(constants.API_URL + '/' + constants.GRAPH_ID + '/gremlin' , json.dumps(data))
    if response.status_code == 200:
        print 'Successfully deleted Buys edges, Print vertexes, and User vertexes'
    else:
        raise ValueError('An error occurred while deleting the vertexes and/or edges for the graph %s: %s. %s'%
                             (constants.GRAPH_ID, response.status_code, response.content))