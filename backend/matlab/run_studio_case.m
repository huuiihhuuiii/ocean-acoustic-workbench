function run_studio_case
% Fixed entry point: numeric JSON configuration, audited Munk environment.
cfg = jsondecode(fileread('case.json'));
if ~isfield(cfg,'mode_addition'),cfg.mode_addition='incoherent';end
addpath(cfg.toolbox_path, fullfile(cfg.toolbox_path,'bin'),fullfile(cfg.toolbox_path,'ReadWrite'),fullfile(cfg.toolbox_path,'Misc'));
if isfield(cfg,'environment_snapshot')
    assert(isfile('case.env'),'Custom ENV missing');
    water_depth=cfg.water_depth_m;
else
water_depth=5000;
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
end
fid=fopen('case.flp','w');
field_option='RCOI';if isfield(cfg,'mode_addition') && strcmp(cfg.mode_addition,'coherent'),field_option='RCOC';end
fprintf(fid,"/\n'%s'\n9999\n1\n0.0 /\n%d\n%.9g %.9g /\n1\n%.9g /\n%d\n0.0 %.9g /\n1\n0.0 /\n",field_option,cfg.range_points,cfg.range_min_km,cfg.range_max_km,cfg.source_depth_m,cfg.depth_points,water_depth);
fclose(fid);
[~, f, SSP, Bdry, P] = read_env('case.env','KRAKEN');
assert(abs(f-cfg.frequency_hz)<1e-6 && abs(P.s.depth(1)-cfg.source_depth_m)<1e-4,'ENV roundtrip mismatch');
assert(abs(Bdry.Bot.depth-water_depth)<1e-4,'ENV water depth mismatch');
if isfield(cfg,'environment_snapshot')
    expected_z=[cfg.environment_snapshot.ssp.depth_m]';
    expected_c=[cfg.environment_snapshot.ssp.sound_speed_m_s]';
    assert(numel(SSP.z)==numel(expected_z),'SSP layer count mismatch');
    assert(max(abs(double(SSP.z(:))-expected_z))<1e-4,'SSP depth mismatch');
    assert(max(abs(real(double(SSP.c(:)))-expected_c))<1e-6,'SSP sound speed mismatch');
end
fprintf('OCEAN_STAGE: INPUT_VALIDATED\n');
if isfield(cfg,'solver') && strcmp(cfg.solver,'scooter')
    % Rebuild only numeric controls; keep the frozen SSP and fluid boundaries.
    raw=splitlines(string(fileread('case.env')));
    bi=find(startsWith(strtrim(raw),"'A'"),1);
    assert(~isempty(bi),'Bottom boundary missing');
    prefix=raw(1:bi+1);prefix(4)="'CVW'";
    prefix(5)=string(cfg.scooter_mesh_points)+" 0.0 "+string(water_depth);
    cmin=min([cfg.environment_snapshot.ssp.sound_speed_m_s])*0.9;
    cmax=max([cfg.environment_snapshot.bottom.speed_m_s,cfg.environment_snapshot.ssp.sound_speed_m_s])*1.1;
    rmax=cfg.range_max_km*cfg.scooter_rmax_factor;
    fid=fopen('case.env','w');fprintf(fid,'%s\n',prefix);
    fprintf(fid,"%.9g %.9g\n%.9g\n1\n%.9g /\n%d\n0.0 %.9g /\n",cmin,cmax,rmax,cfg.source_depth_m,cfg.depth_points,water_depth);fclose(fid);
    fid=fopen('case.flp','w');fprintf(fid,"'RP'\n%d\n%.9g %.9g /\n",cfg.range_points,cfg.range_min_km,cfg.range_max_km);fclose(fid);
    addpath(fullfile(cfg.toolbox_path,'Scooter'));
    scooter('case'); % Installed AT wrapper: scooter.exe then MATLAB fieldsco.
    assert(isfile('case.grn') && isfile('case.shd.mat'),'Missing SCOOTER output');
    write_field_result('case.shd.mat',cfg,water_depth,'scooter','RP','coherent');return
end
if isfield(cfg,'solver') && strcmp(cfg.solver,'bellhop')
    raw=splitlines(string(fileread('case.env')));
    bi=find(startsWith(strtrim(raw),"'A'"),1);
    assert(~isempty(bi),'Bottom boundary missing');
    prefix=raw(1:bi+1);prefix(4)="'CVW'";
    output='rays';if isfield(cfg,'bellhop_output'),output=cfg.bellhop_output;end
    run_type='R';beams=cfg.ray_count;
    if ~strcmp(output,'rays')
        run_type='Cg';if strcmp(output,'incoherent'),run_type='Ig';end
        beams=cfg.beam_count;
    end
    fid=fopen('rays.env','w');fprintf(fid,'%s\n',prefix);
    fprintf(fid,"1\n%.9g /\n%d\n0.0 %.9g /\n%d\n%.9g %.9g /\n'%s'\n%d\n%.9g %.9g /\n%.9g %.9g %.9g\n",cfg.source_depth_m,cfg.depth_points,water_depth,cfg.range_points,cfg.range_min_km,cfg.range_max_km,run_type,beams,cfg.angle_min_deg,cfg.angle_max_deg,cfg.ray_step_m,water_depth+100,cfg.range_max_km+0.1);fclose(fid);
    [~,bf,~,bb,bp]=read_env('rays.env','BELLHOP');
    assert(abs(bf-cfg.frequency_hz)<1e-6 && abs(bb.Bot.depth-water_depth)<1e-4 && abs(bp.s.depth(1)-cfg.source_depth_m)<1e-4,'BELLHOP ENV mismatch');
    bellhop('rays');
    if ~strcmp(output,'rays')
        assert(isfile('rays.shd'),'Missing BELLHOP SHD');
        write_field_result('rays.shd',cfg,water_depth,'bellhop',run_type,output);return
    end
    assert(isfile('rays.ray') && isfile('rays.prt'),'Missing BELLHOP output');
    result=struct('solver','bellhop','frequency_hz',cfg.frequency_hz,'source_depth_m',cfg.source_depth_m,'water_depth_m',water_depth,'environment_type',cfg.template,'matlab_version',version,'reference','BELLHOP geometric ray paths; C-linear SSP; no transmission-loss calculation');
    fid=fopen('result.json','w','n','UTF-8');fprintf(fid,'%s',jsonencode(result));fclose(fid);
    fprintf('OCEAN_STAGE: RAYS_WRITTEN\n');return
end
kraken('case');
assert(isfile('case.shd') && isfile('case.prt'),'Missing solver output');
clear read_modes_bin
modes=read_modes('case.mod',cfg.frequency_hz);
assert(modes.M>0 && all(isfinite(real(modes.k))),'Invalid modal output');
n=min(8,numel(modes.k));
modal=struct('count',modes.M,'depths_m',double(modes.z(:))','shape_real',double(real(modes.phi(:,1:n))),'wavenumber_real_rad_m',double(real(modes.k(:)))','wavenumber_imag_rad_m',double(imag(modes.k(:)))','displayed_count',n);
fid=fopen('modes.json','w');fprintf(fid,'%s',jsonencode(modal));fclose(fid);
writetable(table((1:numel(modes.k))',double(real(modes.k(:))),double(imag(modes.k(:))),'VariableNames',{'mode','k_real_rad_m','k_imag_rad_m'}),'modes.csv');
write_field_result('case.shd',cfg,water_depth,'kraken',field_option,cfg.mode_addition);
end

function write_field_result(shd,cfg,water_depth,solver,option,addition)
[title,~,freq,~,pos,pressure] = read_shd(shd,cfg.frequency_hz);
p = reshape(pressure(1,1,:,:),numel(pos.r.depth),numel(pos.r.range));
assert(any(isfinite(real(p(:)))) && any(abs(p(:))>0),'Invalid pressure output');
assert(abs(freq(1)-cfg.frequency_hz)<1e-4,'Frequency mismatch');
assert(abs(double(pos.r.depth(end))-water_depth)<1e-3,'Output depth mismatch');
tl = -20*log10(abs(p));
% Surface pressure is nominally zero; omit near-zero numerical remnants.
tl(~isfinite(tl) | abs(p)<1e-12) = NaN;
[depth_error,ri] = min(abs(double(pos.r.depth)-cfg.receiver_depth_m));
result=struct('title',strtrim(title),'frequency_hz',double(freq(1)), 'source_depth_m',double(pos.s.depth(1)), 'requested_receiver_depth_m',cfg.receiver_depth_m, 'actual_receiver_depth_m',double(pos.r.depth(ri)), 'receiver_depth_error_m',double(depth_error), 'ranges_m',double(pos.r.range(:))', 'depths_m',double(pos.r.depth(:))', 'tl_db',double(tl), 'curve_tl_db',double(tl(ri,:)), 'valid_ratio',sum(isfinite(tl(:)))/numel(tl),'reference','AT FIELD normalized amplitude; TL = -20 log10 |p|; incoherent modal addition (RCOI)','matlab_version',version,'shape',size(tl));
result.environment_type=cfg.template;
result.solver=solver;result.field_options=option;result.mode_addition=addition;
result.reference=[upper(solver) ' normalized amplitude; TL = -20 log10 |p|; ' addition ' (' option ')'];
if strcmp(solver,'kraken'),m=jsondecode(fileread('modes.json'));result.mode_count=m.count;elseif strcmp(solver,'bellhop'),result.bellhop_output=addition;result.beam_count_requested=cfg.beam_count;else,result.integration_rmax_km=cfg.range_max_km*cfg.scooter_rmax_factor;result.mesh_points_requested=cfg.scooter_mesh_points;end
result.water_depth_m=water_depth;
if isfield(cfg,'environment_snapshot')
    result.environment=cfg.environment_snapshot;
end
fid=fopen('result.json','w','n','UTF-8');fprintf(fid,'%s',jsonencode(result));fclose(fid);
curve=table(double(pos.r.range(:)),double(tl(ri,:))','VariableNames',{'range_m','tl_db'});
writetable(curve,'curve.csv');
fprintf('OCEAN_STAGE: RESULT_VALIDATED %d x %d\n',size(tl));
end
