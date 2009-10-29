RAILS_ENV = 'production'
require File.dirname(__FILE__) + '/../config/environment'
  
  #All coordinates are (lon,lat)  (x,y)
  # Atlantic #################
  #Central West North Atlantic
  CWNA	= [[-70.617,35.317 ],[-70.45,47.217],[ -27.383,47.217],[-27.383,40.317 ],[-8.9, 38.633],[ -46.5,35.317],[-70.617,35.317]]
  #North West North Atlantic
  NWNA	= [[-36.967, 65.383],[-24.633, 65.383],[-24.633, 60.583],[-37.5, 52.85],[-27.383, 49.35],[-27.383, 47.217],[-70.617, 47.217],[-70.8, 55.967],[-36.967, 65.383]]
  #North East North Atlantic
  NENA	= [[-5.283, 60.033],[-7.3, 60.033],[-13.583, 65.017],[-24.633, 65.383],[-36.967, 65.383],[-16.717, 81.183],[19.383, 78.633],[-5.283, 60.033]]
  #Central East North Atlantic
  CENA	= [[ -24.633,60.583],[ -37.5,52.85],[-27.383,49.35],[ -27.383,40.317],[ -36.5, 38.633],[-8.9,38.633],[-5.283,60.033],[-7.3,60.033],[-13.583,65.017 ],[-24.633,65.383 ],[-24.633,60.583 ]]
  #South West North Atlantic
  SWNA	= [[-70.5,35.317 ],	[-70.5,11.2 ],	[-81.717,8.23 ],	[-100.883,22.2 ],	[-75.33,35.317 ],	[-70.5,35.317 ]]
  # South North Atlantic
  SNA	  = [[-70.5,35.317 ],	[-70.5,11.2 ],	[-48.167,-0.133 ],	[-19.917,-0.633 ],	[-48.35,12.217 ],	[-48.35,31.217],[-46.5,35.317],	[-70.5,35.317 ]]
  #South East North Atlantic
  SENA	= [[9.3,-0.633 ],	[-19.917,-0.633 ],	[-48.35,12.217 ],	[-48.35,31.217 ],	[-46.5,35.317 ],	[-36.5,38.633 ],	[-8.9,38.633 ],	[9.3,-0.633 ]]
  #North West South Atlantic
  NWSA	= [[-48.167,-0.633 ],	[-19.917,-0.633 ],	[-16.917,-0.633 ],	[-16.917,-30.15 ],	[-49.65,-30.15 ],	[-48.167,-0.633 ]]
  #North East South Atlantic
  NESA	= [[9.3,-0.633],[-16.917,-0.633],[-16.917,-30.15],[-18.183,-30.15],[-18.183,-47.45],[-13.917,-47.433],[-13.917,-55.067],[46.933,-55.067],[42.933,-12.25],[9.3,-0.633]]
  #Central West South Atlantic
  CWSA	= [[-49.65,-30.15],[-18.183,-30.15],[-18.183,-47.45],[-13.917,-47.433],[-13.917,-55.067],[-65.4,-55.067],[-68.867,-47.45],[-49.65,-30.15]]
  #South South Atlantic
  SSA	  = [[-65.4,-55.067],[-65.4,-77.233],[42.933,-73.117],[42.933,-55.067],[-65.4,-55.067]]
  ## PACIFIC #################
  # South East South Pacific
  SESP	= [[-74.867, -49.317],[-74.867, -73.267],[-180, -73.267],[-180,-49.317],[-74.867,-49.317]]
  # South West South Pacific
  SWSP  = [[104.033, -66.917],[104.033, -49.317],[180, -49.317],[180, -66.917],[104.033, -66.917]]
  # West North Pacific
  WNP	  = [[130.55, 42.767],[160.067, 42.767],[160.067, 0.983],[118.783, 0.983],[101.417, 17.917],[130.55, 42.767]]
  # Central North Pacific
  CNP	  = [[160.067, 42.767],[-139.75, 72.767],[-139.75, 0.983],[160.067, 0.983],[160.067, 42.767]]													
  # East North Pacific
  ENP	  = [[-123.733, 42.767],[-139.75, 42.767],[-139.75, 0.983],[-79.833, -0.45],[-81.717, 8.23],[-123.733, 42.767]]														
  # West South Pacific
  WSP	  = [[118.783, 0.983],[-160.183, 0.983],[-160.183, -49.317],[104.03, -49.317],[118.783, 0.983]]														
  # Central South Pacific
  CSP	  = [[-160.183, 0.983],[-160.183, -49.317],[-105.083, -49.317],[-105.083, 0.983],[-160.183, 0.983]]														
  # East South Pacific
  ESP	  = [[-79.833, -0.45],[-105.083, 0.983],[-105.083, -49.317],[-74.867, -49.317],[-67.8, -20.183],[-79.833, -0.45]]													
  # North North Pacific
  NNP	  = [[-123.73,42.767],[130.55,42.767],[109.917,67.767],[-121.233,67.65],[-123.73,42.767]]
  

  Basins = {
    'Central West North Atlantic' => CWNA,
    'North West North Atlantic' => NWNA,
    'North East North Atlantic' => NENA,
    'Central East North Atlantic' => CENA,
    'South West North Atlantic' => SWNA,
    'South North Atlantic' => SNA,
    'South East North Atlantic' => SENA,
    'North West South Atlantic' => NWSA,
    'North East South Atlantic' => NESA,
    'Central West South Atlantic' => CWSA,
    'South South Atlantic'  => SSA,
    'South East South Pacific' => SESP,
    'South West South Pacific' => SWSP,
    'West North Pacific' => WNP,
    'North North Pacific' => NNP,
    'Central North Pacific' => CNP,
    'East North Pacific' => ENP,
    'West South Pacific' => WSP,
    'Central South Pacific' => CSP,
    'East South Pacific' => ESP
  }

  for key in Basins.keys
    @basin = Basin.new()
    poly = Polygon.from_coordinates([Basins[key]])
    @basin.Description = poly
    @basin.Name = "#{key}"
    #@basin.save
  end