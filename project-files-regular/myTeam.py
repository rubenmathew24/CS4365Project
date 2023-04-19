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
from util import nearestPoint
import math

#################
# Team creation #
#################

def createTeam(firstIndex, secondIndex, isRed,
               first = 'DefensiveAgent', second = 'DefensiveAgent'):

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
    
    # Find exit tiles, sorted by distance from center
    if not hasattr(self, 'exits'):
      self.exits = []
      
      # Find borders
      teamBorder = math.floor(self.middleWidth) - 1
      enemyBorder = math.floor(self.middleWidth)
      if not gameState.isOnRedTeam(self.index):
        teamBorder = math.floor(self.middleWidth)
        enemyBorder = math.floor(self.middleWidth) - 1
      
      # Determine if each border tile is exit (both sides open)
      for y in range(walls.height):
        if not walls[teamBorder][y] and not walls[enemyBorder][y]:
          self.exits.append((teamBorder, y))
      
      # Sort by distance from center
      self.exits = sorted(self.exits, key = lambda exit : (abs(self.middleHeight - exit[1])))
      

  def chooseAction(self, gameState):
    # Built-in get possible actions
    actions = gameState.getLegalActions(self.index)

    # Evaluate each action for h value
    start = time.time()
    values = [self.evaluate(gameState, a) for a in actions]
    print('eval time for agent %d: %.4f' % (self.index, time.time() - start))

    # Find actions of max value
    maxValue = max(values)
    bestActions = [a for a, v in zip(actions, values) if v == maxValue]
    return random.choice(bestActions)   # Return random best action
  
  def evaluate(self, gameState, action):
    # Determines value based on features and their weights
    features = self.getFeatures(gameState, action)
    weights = self.getWeights(gameState, action)
    #print(features * weights)
    return features * weights

class DefensiveAgent(DummyAgent):
  
  def getFeatures(self, gameState, action):
    # Successor info
    succ = self.getSuccessor(gameState, action)
    succState = succ.getAgentState(self.index)
    succPos = succState.getPosition()

    # Features
    features = util.Counter()
    features['disToRiskyExit'] = self.distancer.getDistance(succPos, self.getRiskyExit(gameState, self.exits))    # Succ's distance from risky exit (exit an enemy is closest to)
    features['enemy'] = 1 if (succPos == gameState.getAgentPosition(self.enemyIndices[0]) or succPos == gameState.getAgentPosition(self.enemyIndices[1])) else 0
    return features
  
  def getWeights(self, gameState, action):
    return {
      'disToRiskyExit': -1, # Base weight, keeps agent close to exits & border
      'enemy': 1000         # If can eat enemy, do it  
    }
  
  # Finds risky exit (exit that offensive enemy can reach fastest, prefer exits closer to center)
  def getRiskyExit(self, gameState, exits):
    distances = [10000 for exit in exits]   # Init with large value to prefer lowest distances later
    # Only check with offensive enemies
    for enemy in self.enemyIndices:
      enemyPos = gameState.getAgentPosition(enemy)
      if self.inTeamSide(enemyPos):
        # Find distance between enemy and every exit
        for exit in range(len(exits)):
          distances[exit] = min(distances[exit], self.distancer.getDistance(exits[exit], enemyPos)) # Store min distance between existing & new to account for multiple offensive

    return exits[distances.index(min(distances))] # return exit with lowest distance
  
  # Determines if agent is on our team's side
  def inTeamSide(self, pos):
    if self.redTeam: 
      return pos[0] in range(math.floor(self.middleWidth))
    else:
      return pos[0] in range(math.floor(self.middleWidth), self.mapWidth)
    
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