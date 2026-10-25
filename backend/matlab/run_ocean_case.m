function run_ocean_case
% Fixed entry point: numeric JSON configuration, audited Munk environment.
cfg = jsondecode(fileread('case.json'));
addpath(cfg.toolbox_path, fullfile(cfg.toolbox_path,'bin'),fullfile(cfg.toolbox_path,'ReadWrite'),fullfile(cfg.toolbox_path,'Misc'));
raw = splitlines(string(fileread(cfg.template_env)));
raw = raw(strlength(strtrim(raw)) > 0);
% The packaged Munk template's structural landmarks are checked before edits.
assert(contains(raw(1),'Munk') && str2double(raw(3)) == 1,'Unexpected Munk template');
idx = find(contains(raw,'! NSD'),1);
assert(~isempty(idx),'Source depth marker missing');
raw(2) = string(cfg.frequency_hz);
raw(idx) = "1 ! NSD";
raw(idx+1) = string(cfg.source_depth_m) + " / ! SD";
fid=fopen('case.env','w'); fprintf(fid,'%s\n',raw); fclose(fid);
fid=fopen('case.flp','w');
fprintf(fid,"/\n'RCOI'\n9999\n1\n0.0 /\n%d\n%.9g %.9g /\n1\n%.9g /\n%d\n0.0 5000.0 /\n1\n0.0 /\n",cfg.range_points,cfg.range_min_km,cfg.range_max_km,cfg.source_depth_m,cfg.depth_points);
fclose(fid);
[~, f, ~, ~, P] = read_env('case.env','KRAKEN');
assert(abs(f-cfg.frequency_hz)<1e-6 && abs(P.s.depth(1)-cfg.source_depth_m)<1e-4,'ENV roundtrip mismatch');
fprintf('OCEAN_STAGE: INPUT_VALIDATED\n');
kraken('case');
assert(isfile('case.shd') && isfile('case.prt'),'Missing solver output');
[title,~,freq,~,pos,pressure] = read_shd('case.shd',cfg.frequency_hz);
p = reshape(pressure(1,1,:,:),numel(pos.r.depth),numel(pos.r.range));
assert(any(isfinite(real(p(:)))) && any(abs(p(:))>0),'Invalid pressure output');
assert(abs(freq(1)-cfg.frequency_hz)<1e-4,'Frequency mismatch');
tl = -20*log10(abs(p));
% Surface pressure is nominally zero; omit near-zero numerical remnants.
tl(~isfinite(tl) | abs(p)<1e-12) = NaN;
[depth_error,ri] = min(abs(double(pos.r.depth)-cfg.receiver_depth_m));
result=struct('title',strtrim(title),'frequency_hz',double(freq(1)), 'source_depth_m',double(pos.s.depth(1)), 'requested_receiver_depth_m',cfg.receiver_depth_m, 'actual_receiver_depth_m',double(pos.r.depth(ri)), 'receiver_depth_error_m',double(depth_error), 'ranges_m',double(pos.r.range(:))', 'depths_m',double(pos.r.depth(:))', 'tl_db',double(tl), 'curve_tl_db',double(tl(ri,:)), 'valid_ratio',sum(isfinite(tl(:)))/numel(tl),'reference','AT FIELD normalized pressure; TL = -20 log10 |p|; coherent modal field','matlab_version',version,'shape',size(tl));
fid=fopen('result.json','w','n','UTF-8');fprintf(fid,'%s',jsonencode(result));fclose(fid);
curve=table(double(pos.r.range(:)),double(tl(ri,:))','VariableNames',{'range_m','tl_db'});
writetable(curve,'curve.csv');
fprintf('OCEAN_STAGE: RESULT_VALIDATED %d x %d\n',size(tl));
end
