% Shared structural checks. This is not a physical accuracy certificate.
assert(isfile(workflow_output),'Expected fresh model output missing');
[PlotTitle,PlotType,freqVec,atten,Pos,pressure]=read_shd(workflow_output);
assert(any(isfinite(pressure(:)) & abs(pressure(:))>0),'No finite nonzero field');
nz=size(pressure,3); nr=size(pressure,4);
assert(numel(Pos.r.depth)==nz && numel(Pos.r.range)==nr,'Coordinate dimensions disagree');
slice=reshape(pressure(1,1,:,:),nz,nr);
level=-20*log10(abs(slice)); level(~isfinite(level))=NaN;
assert(any(isfinite(level(:))),'Selected slice has no finite field');
relative=strcmp(workflow_axis,'time_s');
if relative, label='Relative amplitude level (dB; source normalization required)'; else, label='TL (dB; AT source convention)'; end
save('model_pressure.mat','PlotTitle','PlotType','freqVec','atten','Pos','pressure','workflow_axis','-v7');
[R,Z]=meshgrid(Pos.r.range,Pos.r.depth);
writematrix([R(:),Z(:),level(:)],'field_slice.csv');
figure('Visible','off'); imagesc(Pos.r.range/1000,Pos.r.depth,level); set(gca,'YDir','reverse'); colorbar;
xlabel('Range (km)'); ylabel('Receiver depth (m)'); title([workflow_model ' | ' label],'Interpreter','none');
exportgraphics(gcf,'field_slice.png','Resolution',150); close all;
metrics=struct('model',workflow_model,'output',workflow_output,'frequency_or_carrier_hz',freqVec,'pressure_shape',size(pressure),'finite_ratio',sum(isfinite(pressure(:)))/numel(pressure),'selected_bearing_index',1,'selected_source_or_time_index',1,'source_axis',workflow_axis,'level_label',label,'csv_columns',{{'range_m','receiver_depth_m','level_db'}},'scope','Execution and output structure checked; convergence and physical accuracy need separate evidence');
if relative, metrics.selected_time_s=Pos.s.depth(1); else, metrics.selected_source_depth_m=Pos.s.depth(1); end
fid=fopen('model_metrics.json','w'); assert(fid>=0); fwrite(fid,jsonencode(metrics)); fclose(fid);
disp('MODEL_WORKFLOW_OUTPUT_CHECKED');
