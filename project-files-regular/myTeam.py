"""
PacMan CTF AI
CS 4365 Final Project
By Ruben & Daniel
"""

from captureAgents import CaptureAgent
import random, time, util
from game import Directions
import game
from distanceCalculator import Distancer
from util import nearestPoint, manhattanDistance, PriorityQueueWithFunction
import math
import sys

BIG_NUMBER = 10000

#################
# Team creation #
#################

def createTeam(firstIndex, secondIndex, isRed,
               first = 'DefensiveAgent', second = 'OffensiveAgent'):

  return [eval(first)(firstIndex), eval(second)(secondIndex)]

##########
# Agents #
##########

class DummyAgent(CaptureAgent):

  def registerInitialState(self, gameState):

    # Built-in register, provides real distancer
    CaptureAgent.registerInitialState(self, gameState)

    # Determine team/side
    self.redTeam = gameState.isOnRedTeam(self.index)
    
    # Indices of each agent
    self.teamIndices = gameState.getRedTeamIndices()
    self.enemyIndices = gameState.getBlueTeamIndices()
    if not self.redTeam:
      self.teamIndices = gameState.getBlueTeamIndices()
      self.enemyIndices = gameState.getRedTeamIndices()

    # Important positions
    self.startPos = gameState.getAgentPosition(self.index)
    walls = gameState.getWalls()
    self.middleWidth = walls.width / 2    # True middle
    self.middleHeight = walls.height / 2  # True middle
    self.mapWidth = walls.width

    # Find borders
    self.teamBorder = math.floor(self.middleWidth) - 1
    self.enemyBorder = math.floor(self.middleWidth)
    if not gameState.isOnRedTeam(self.index):
      self.teamBorder = math.floor(self.middleWidth)
      self.enemyBorder = math.floor(self.middleWidth) - 1
    
    # Find exit tiles, sorted by distance from center
    if not hasattr(self, 'exits'):
      self.gaps = [] 
      # Determine if each border tile is exit (both sides open)
      for y in range(walls.height):
        if not walls[self.teamBorder][y] and not walls[self.enemyBorder][y]:
          self.gaps.append((self.teamBorder, y))
      
  def chooseAction(self, gameState):
    # Built-in get possible actions
    actions = gameState.getLegalActions(self.index)

    # Evaluate each action for h value
    start = time.time()
    values = [self.evaluate(gameState, a) for a in actions]
    #print('eval time for agent %d: %.4f' % (self.index, time.time() - start))

    # Find actions of max value
    bestValue = max(values)
    bestActions = [a for a, v in zip(actions, values) if v == bestValue]
    #print(type(self), "Best Actions:", bestActions, "Best Value:", bestValue)
    #print(list(zip(actions,values)))
    return random.choice(bestActions)   # Return random best action
  
  def evaluate(self, gameState, action):
    # Determines value based on features and their weights
    features = self.getFeatures(gameState, action)
    weights = self.getWeights(gameState, action)
    #print("\n","\t"+action + ": " + str(features * weights), "F: " + str(features), "W: " + str(weights), "\n", sep="\n\t")
    return features * weights
  
  def getSuccessor(self, gameState, action):
    """
    Finds the next successor which is a grid position (location tuple).
    """
    successor = gameState.generateSuccessor(self.index, action)
    pos = successor.getAgentState(self.index).getPosition()
    if pos != nearestPoint(pos):
      # Only half a grid position was covered
      return successor.generateSuccessor(self.index, action)
    else:
      return successor

  # Determines if agent is on our team's side
  def onTeamSide(self, pos):
    if self.redTeam: 
      return pos[0] in range(math.floor(self.middleWidth))
    else:
      return pos[0] in range(math.floor(self.middleWidth), self.mapWidth)

class OffensiveAgent(DummyAgent):

  def registerInitialState(self, gameState):
    DummyAgent.registerInitialState(self, gameState)

    self.totalFood = len(self.getFood(gameState).asList())

    # Save the default weights because weights can be changed
    self.defaults = {'eatFood': 100, # Prioritize eating food
                    'eatCapsule': 2000, # Prioritize eating capsules
                    'distanceToCapsule': -40,  # Prioritize getting close to capsules
                    'distanceToFood': -15,  # Prioritize getting close to food
                    'distanceToExit': -1,  # Prioritize getting close to exit
                    'notableDistanceFromEnemy' : -25, # Prioritize getting far from enemy
                    'neverStop' : -1, # Be a shark, never stop moving
                    'onOurSide' : -10, # Discourage staying on our side
                    'quickGetaway' : 100 # If can quickly deposit food, do it
                    }

    # Weights that will be returned
    self.weights = {'eatFood': self.defaults['eatFood'], 
                    'eatCapsule': self.defaults['eatCapsule'], 
                    'distanceToCapsule': self.defaults['distanceToCapsule'], 
                    'distanceToFood': self.defaults['distanceToFood'], 
                    'distanceToExit': self.defaults['distanceToExit'], 
                    'notableDistanceFromEnemy': self.defaults['notableDistanceFromEnemy'], 
                    'neverStop': self.defaults['neverStop'],
                    'onOurSide': self.defaults['onOurSide'],
                    'quickGetaway': self.defaults['quickGetaway']
                    }

  def getFeatures(self, gameState, action):
    features = util.Counter()
    successor = self.getSuccessor(gameState, action)
    foodList = self.getFood(successor).asList()  
    capsuleList = self.getCapsules(successor)
    enemyList = self.getOpponents(successor)
    myPos = successor.getAgentState(self.index).getPosition()
    numCarrying = gameState.getAgentState(self.index).numCarrying


    # Prioritize not being our side unless its an exit
    if self.onTeamSide(myPos) and myPos not in self.gaps:
      features['onOurSide'] = 1

    # Prioritize eating food
    features['eatFood'] = -len(foodList)

    # Priortize eating capsules
    features['eatCapsule'] = -len(capsuleList)

    # Compute distance to the nearest capsule
    if len(capsuleList) > 0: 
      minDistance = min([self.getMazeDistance(myPos, capsule) for capsule in capsuleList])
      features['distanceToCapsule'] = minDistance

      # DEBUG draw the closest capsule
      for capsule in capsuleList:
        if self.getMazeDistance(myPos, capsule) == minDistance:
          self.debugDraw(capsule, [0,0.8,0.8])

    # Compute distance to the nearest food
    if len(foodList) > 0: # This should always be True,  but better safe than sorry
      minDistance = min([self.getMazeDistance(myPos, food) for food in foodList])

      # DEBUG draw the closest food
      closestFood = None
      for food in foodList:
        if self.getMazeDistance(myPos, food) == minDistance:
          closestFood = food
          self.debugDraw(food, [0.5,0.5,0])
        
      # less food available, more likely to be spread apart, so don't worry as much about distance
      self.weights['distanceToFood'] = self.defaults['distanceToFood'] * ((len(foodList) / self.totalFood))
      if self.getScore(successor) > 0: self.weights['distanceToFood'] = -5

      # If enemies are not close to food, priortize it MORE
      if len(enemyList) > 0:
        minDistanceToEnemy = min([manhattanDistance(closestFood, successor.getAgentState(enemy).getPosition()) for enemy in enemyList])
        if minDistanceToEnemy > 5:
          self.weights['distanceToFood'] = self.weights['distanceToFood'] * 3

      features['distanceToFood'] = minDistance

    # Compute distance to the nearest exit
    minDistanceToExit = 1000
    if len(self.gaps) > 0: # This should always be True,  but better safe than sorry
      minDistance = min([self.getMazeDistance(myPos, exit) for exit in self.gaps])
      minDistanceToExit = minDistance
      features['distanceToExit'] += minDistance * max(features['notableDistanceFromEnemy'], 1)

    # Increase weight of distance to exit with the more food we have
    self.weights['distanceToExit'] = -numCarrying*5

    # If can make a quick getaway, do it
    currentDistanceFromExit = min([self.getMazeDistance(gameState.getAgentState(self.index).getPosition(), exit) for exit in self.gaps])
    if numCarrying >= 2 and currentDistanceFromExit < 5:
      features = util.Counter()
      features['quickGetaway'] = 2
      features['distanceToExit'] = minDistanceToExit
      return features

    # Stops it from stalling
    if action == Directions.STOP: features['neverStop'] += 9999999

    # Compute distance to the nearest enemy (only appropriate if we're on the enemy's side)
    actualDistanceFromEnemy = 1000
    if len(enemyList) > 0:
      minDistance = min([manhattanDistance(myPos, successor.getAgentState(enemy).getPosition()) for enemy in enemyList])
      actualDistanceFromEnemy = min([self.getMazeDistance(myPos, successor.getAgentState(enemy).getPosition()) for enemy in enemyList])

      # If on our side, keep a lower distance away from enemy
      features['notableDistanceFromEnemy'] = max((3 if self.onTeamSide(myPos) else 5)-minDistance, 0)
      if actualDistanceFromEnemy > minDistance + 5: features['notableDistanceFromEnemy'] = 0

      # If enemy is FAR away, don't increase food weight
      if actualDistanceFromEnemy > 15: 
        self.weights['distanceToFood'] = self.weights['distanceToFood'] * 3

      # If enemy is incredibly close, prioritize getting away
      if actualDistanceFromEnemy < 3 and currentDistanceFromExit > 3: self.weights['notableDistanceFromEnemy'] = -100
      else: self.weights['notableDistanceFromEnemy'] = self.defaults['notableDistanceFromEnemy']

    # If capsule is active
    scaredTime = max([(successor.getAgentState(enemy).scaredTimer) for enemy in enemyList])
    if scaredTime > 0:
      # If we're carrying food, prioritize getting home
      if numCarrying > 4: self.weights['distanceToExit'] = -100
      else: self.weights['distanceToExit'] = -numCarrying * 10

      # Try not to get other capsules
      self.weights['distanceToCapsule'] = 5

      # Chase enemy if they're close AND if timer isn't low
      if scaredTime > 15:
        print(currentDistanceFromExit)
        features['notableDistanceFromEnemy'] = -features['notableDistanceFromEnemy'] * 60
        if actualDistanceFromEnemy == 0: features['notableDistanceFromEnemy'] = -3000
      if currentDistanceFromExit > 15:
        features['notableDistanceFromEnemy'] = 0  

    # Reset weights if capsule not active
    else:
      self.weights['distanceToCapsule'] = self.defaults['distanceToCapsule']


    return features

  def getWeights(self, gameState, action):
    return self.weights

class DefensiveAgent(DummyAgent):
  def registerInitialState(self, gameState):

    # Built-in register, provides real distancer
    CaptureAgent.registerInitialState(self, gameState)

    # Determine team/side
    self.redTeam = gameState.isOnRedTeam(self.index)
    
    # Indices of each agent
    self.teamIndices = gameState.getRedTeamIndices()
    self.enemyIndices = gameState.getBlueTeamIndices()
    if not self.redTeam:
      self.teamIndices = gameState.getBlueTeamIndices()
      self.enemyIndices = gameState.getRedTeamIndices()

    # Important positions
    self.startPos = gameState.getAgentPosition(self.index)
    walls = gameState.getWalls()
    self.middleWidth = walls.width / 2    # True middle
    self.middleHeight = walls.height / 2  # True middle
    self.mapWidth = walls.width

    # Find borders
    self.teamBorder = math.floor(self.middleWidth) - 1
    self.enemyBorder = math.floor(self.middleWidth)
    if not gameState.isOnRedTeam(self.index):
      self.teamBorder = math.floor(self.middleWidth)
      self.enemyBorder = math.floor(self.middleWidth) - 1
    
    # Find exit tiles, sorted by distance from center
    if not hasattr(self, 'exits'):
      self.gaps = [] 
      # Determine if each border tile is exit (both sides open)
      for y in range(walls.height):
        if not walls[self.teamBorder][y] and not walls[self.enemyBorder][y]:
          self.gaps.append((self.teamBorder, y))
      
    # Enemy Info
    enemy1Index = self.enemyIndices[0]
    self.enemy1 = {}
    self.enemy1['index'] = enemy1Index
    self.enemy1['pos'] = gameState.getAgentPosition(self.enemy1['index'])
    self.enemy1['movesSpentAttacking'] = 0

    enemy2Index = self.enemyIndices[1]
    self.enemy2 = {}
    self.enemy2['index'] = enemy2Index
    self.enemy2['pos'] = gameState.getAgentPosition(self.enemy2['index'])
    self.enemy2['movesSpentAttacking'] = 0

    # Misc Info
    self.quickGrab = False
      
  def chooseAction(self, gameState):
    # Built-in get possible actions
    actions = gameState.getLegalActions(self.index)
    myPos = gameState.getAgentPosition(self.index)

    # Collect enemy info
    enemy1Gaps = self.findClosestGaps(self.enemy1['pos'])
    self.enemy1['gapMain'] = enemy1Gaps[0]
    self.enemy1['gapAlt'] = enemy1Gaps[1]
    self.enemy1['pos'] = gameState.getAgentPosition(self.enemy1['index'])
    self.enemy1['onTeamSide'] = self.onTeamSide(self.enemy1['pos'])
    enemy2Gaps = self.findClosestGaps(self.enemy2['pos'])
    self.enemy2['gapMain'] = enemy2Gaps[0]
    self.enemy2['gapAlt'] = enemy2Gaps[1]
    self.enemy2['pos'] = gameState.getAgentPosition(self.enemy2['index'])
    self.enemy2['onTeamSide'] = self.onTeamSide(self.enemy2['pos'])

    if self.enemy1['onTeamSide']:
      self.enemy1['movesSpentAttacking'] += 1
    if self.enemy2['onTeamSide']:
      self.enemy2['movesSpentAttacking'] += 1
    
    # Look for quick grabs
    if not self.quickGrab:
      foodList = self.getFood(gameState).asList()
      if len(foodList) > 0:
        disToFood = BIG_NUMBER
        for food in foodList:
          foodDis = self.getMazeDistance(myPos, food)
          if foodDis < disToFood:
            disToFood = foodDis
            self.quickGrabPos = food
        disToQuickGrab = disToFood + self.findClosestGaps(self.quickGrabPos)[0][1]
        if disToQuickGrab < min(self.enemy1['gapMain'][1], self.enemy2['gapMain'][1]):
          self.quickGrab = True
        else:
            self.quickGrabPos = None
    if myPos == self.quickGrabPos:
      self.quickGrab = False
      self.quickGrabPos = None
    if self.quickGrabPos:
      self.debugDraw(self.quickGrabPos, [0,1,0])

    # Evaluate each action for h value
    #start = time.time()
    values = [self.evaluate(gameState, a) for a in actions]
    #evalTime = time.time() - start
    #if evalTime > 1:
    #  print('eval time for agent %d took too long!: %.4f' % (self.index, evalTime))
    #  sys.exit()
    #print('eval time for agent %d: %.4f' % (self.index, evalTime))

    # Find actions of max value
    bestValue = max(values)
    bestActions = [a for a, v in zip(actions, values) if v == bestValue]
    #print(type(self), "Best Actions:", bestActions, "Best Value:", bestValue)
    #print(list(zip(actions,values)))
    return random.choice(bestActions)   # Return random best action
  
  def evaluate(self, gameState, action):
    # Determines value based on features and their weights
    features = None
    if self.quickGrab:
      features = self.getFeatures_QuickGrab(gameState, action)
    else:
      features = self.getFeatures(gameState, action)
    weights = self.getWeights(gameState, action)
    #print("\n","\t"+action + ": " + str(features * weights), "F: " + str(features), "W: " + str(weights), "\n", sep="\n\t")
    return features * weights
  
  def getSuccessor(self, gameState, action):
    """
    Finds the next successor which is a grid position (location tuple).
    """
    successor = gameState.generateSuccessor(self.index, action)
    pos = successor.getAgentState(self.index).getPosition()
    if pos != nearestPoint(pos):
      # Only half a grid position was covered
      return successor.generateSuccessor(self.index, action)
    else:
      return successor
  
  def getFeatures(self, gameState, action):
    # Successor info
    succ = self.getSuccessor(gameState, action)
    succState = succ.getAgentState(self.index)
    succPos = succState.getPosition()

    # Enemy Info
    
    self.enemy1['distanceTo'] =  self.getMazeDistance(succPos, self.enemy1['pos'])
    self.enemy2['distanceTo'] = self.getMazeDistance(succPos, self.enemy2['pos'])
    mainEnemy = self.assessEnemies(self.enemy1, self.enemy2)
    self.debugDraw(mainEnemy['pos'], [1,0,0])

    # Draw gaps
    self.debugDraw(self.enemy1['gapMain'][0], [1,0,0], clear=True)
    self.debugDraw(self.enemy1['gapAlt'][0], [1,.4,.4])
    self.debugDraw(self.enemy2['gapMain'][0], [0,1,0])
    self.debugDraw(self.enemy2['gapAlt'][0], [.6,1,.6])

    ### Features ###
    features = util.Counter()
    features['disFromBorder'] = abs(succPos[0] - self.teamBorder)
    features['onEnemySide'] = not self.onTeamSide(succPos)
    features['mainEnemyRisk'] = self.getMazeDistance(succPos, mainEnemy['gapMain'][0])
    features['mainEnemyAltRisk'] = self.getMazeDistance(succPos, mainEnemy['gapAlt'][0])
    features['mainEnemyRiskBalance'] = abs(features['mainEnemyRisk'] - features['mainEnemyAltRisk'])
    features['pop'] = 1 if self.getDisToOffensiveEnemy(gameState, succPos) < 1 else 0
    return features
  
  def getFeatures_QuickGrab(self, gameState, action):
    # Successor info
    succ = self.getSuccessor(gameState, action)
    succState = succ.getAgentState(self.index)
    succPos = succState.getPosition()

    # Features
    features = util.Counter()
    features['disToFood'] = self.getMazeDistance(succPos, self.quickGrabPos)
    return features
  
  def getWeights(self, gameState, action):
    weights = {}
    weights['disFromBorder'] = -1         # Prefer close to border
    weights['mainEnemyRisk'] = -1         # Move towards mainEnemy's mainGap
    weights['mainEnemyAltRisk'] = -1      # Move towards mainEnemy's altGap
    weights['mainEnemyRiskBalance'] = -1  # Prefer in-between of mainEnemy's 2 gaps
    weights['disToOffensiveEnemy'] = -3   # Chase after nearby enemies
    weights['onEnemySide'] = -5           # Discourage entering enemy side when unnecesary
    weights['pop'] = BIG_NUMBER           # If can eat enemy, do it  
    weights['disToFood'] = -1             # For quickgrabbing
    return weights

  def assessEnemies(self, enemy1, enemy2):
    return max((enemy1, enemy2), key = lambda enemy : enemy['movesSpentAttacking'])

  def getDisToOffensiveEnemy(self, gameState, succPos):
    minDis = BIG_NUMBER
    for enemy in self.enemyIndices:
      enemyPos = gameState.getAgentPosition(enemy)
      if self.onTeamSide(enemyPos):
        disToEnemy = self.getMazeDistance(succPos, enemyPos)
        if disToEnemy < minDis:
          minDis = disToEnemy
    return minDis
  
  # Determines if agent is on our team's side
  def onTeamSide(self, pos):
    if self.redTeam: 
      return pos[0] in range(math.floor(self.middleWidth))
    else:
      return pos[0] in range(math.floor(self.middleWidth), self.mapWidth)
    
  # Returns list of gaps sorted by proximity
  def findClosestGaps(self, pos):
    gapDistances = []
    for gap in self.gaps:
      gapDistances.append(self.getMazeDistance(gap, pos))
    gapsByDis = sorted(zip(self.gaps, gapDistances), key=lambda pair : (pair[1], abs(self.middleHeight - pair[0][1])))
    return gapsByDis
