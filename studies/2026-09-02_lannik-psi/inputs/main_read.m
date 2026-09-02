%read paramterers for the RX and TX aperture regarding IFC aperture revA

%load Mat-files

clear all
close all

load('antenna_arr_77_TX_rev_A.mat'); %TX aperture and tapering (excitations)
antenna_arr_TX=antenna_arr;

load('antenna_arr_77_RX_rev_A.mat');  %RX aperture and tapering (excitations)
antenna_arr_RX=antenna_arr;




colstr = {'yd','md','cd','rd','gd','bd','kd','md'};
colstr_tx = {'m*','b*','r*','k*','gs','bs','ks','ms'};

ch_use=[1:8]; %Select apertures to plot
%Read data
x=antenna_arr_RX(:,2);
y=antenna_arr_RX(:,3);
x_tx=antenna_arr_TX(:,2);
y_tx=antenna_arr_TX(:,3);
exc=antenna_arr_RX(:,5);
exc_TX=antenna_arr_TX(:,5);


%plot RX and TX aperture
figure(200);clf;grid on;hold on; title('')
val_use_x=2*0.0157; %displacement between TX and centre
val_use_y=0;
ph(1)=val_use_x; %offset TX
ph(2)=val_use_y; %offset RX

for ch=1:max(antenna_arr(:,6)) %For each sub aperture
    elil = find(antenna_arr(:,6) == ch_use(ch) & exc~=0);
    x_sub{ch}=x(elil)-val_use_x;
    y_sub{ch}=y(elil);
    plot(x_sub{ch},y_sub{ch},colstr{ch},'MarkerSize',5,'LineWidth',2)
end

for ll=1:max(antenna_arr_TX(:,6))    
    elil = find(antenna_arr_TX(:,6) == (ll) & exc_TX~=0); 
    x_subtx=x_tx(elil)+ph(1);
    y_subtx=y_tx(elil)+ph(2);
    plot(x_subtx,y_subtx,colstr_tx{ll},'MarkerSize',10,'LineWidth',2)
end

legend('RX ch 1','RX ch 2','RX ch 3','RX ch 4','RX ch 5','RX ch 6','RX ch 7','RX ch 8',...
       'TX ch 1','TX ch 2','TX ch 3','TX ch 4','TX ch 5','TX ch 6','TX ch 7','TX ch 8','Location','best')

 axis equal
 
   