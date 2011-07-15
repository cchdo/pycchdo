      program sumrd
c
c      intrinsic none
c-----------------------   
      character*1   lathem,lonhem  
      character*3   casttype, nav
      character*5   statcode, stnnum, wocesec
      character*14  expo
      character*132 dummy
c-------------------------
      integer      castnum, statdate, stattime
      integer      latdeg, londeg, bottom
c-------------------------
      real         latmin, lonmin
c-------------------------

      open(10, file='testsum.txt', form='formatted',
     + access='sequential')
c
c===============================================
 100  format(a14,1x,a5,1x,a5,4x,i3,2x,a3,1x,i6.6,
     + 1x,i4.4,3x,a2,
     + 1x,i2,1x,f5.2,1x,a1,
     + 1x,i3,1x,f5.2,1x,a1,
     + 1x,a3,
     + 1x,i5.5)
c================================================

c
c---> READ THE HEADER LINES
c
200   do 300, i=1,4
      read (10,*) dummy
300   continue
          
c
c--> READ THE FIRST LINE.
c--> IF YOU WANT TO READ THEM ALL, LOOP 'EM
c
      read(10,100) expo, wocesec, stnnum, castnum, casttype, statdate,
     +             stattime, statcode, 
     +             latdeg, latmin, lathem,
     +             londeg, lonmin, lonhem,
     +             nav, bottom
          
      print *, 'EXPO is:    ', expo  ,   ' WOCESECT is: ', wocesec 
      print *, 'STNNUM is:  ', stnnum,   ' CASTNO   is: ', castnum 
      print *, 'CASTTYPE is:', casttype, ' DATE     is: ', statdate 
      print *, 'TIME     is:', stattime, ' CODE     is: ', statcode      
      print *, 'LAT(deg) is:', latdeg,   ' LAT(min) is: ', latmin
      print *, 'LAT(hem) is:', lathem
      print *, 'LON(deg) is:', londeg,   ' LON(min) is: ', lonmin      
      print *, 'LON(hem) is:', lonhem
      print *, 'NAV      is: ', nav ,    ' BOTTOM   is: ', bottom
c
                 
      close(10)
      end
