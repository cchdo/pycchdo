%
%
%
%
%
sst1=netcdf('/u/bindoff/sst05d19900108.nc')
%
% display the contents of the variables
%
for i=1:8
  sst1{i}
end
%
% Do a test plot of the data
%
latitude=sst1{'latitude'}(1:end);
longitude=sst1{'longitude'}(1:end);
sst=sst1{'sea_surface_temperature'}(1:end,1:end);
pause
%
pcolor(sst(1:10:end,1:10:end)/100)
caxis([-2 32])
shading flat
%