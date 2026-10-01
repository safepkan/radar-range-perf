function window_convert_infineon(source,target)

%window_convert_infineon: One-time conversion of the 2026-08-27 CARKIT ADC recording
%    The 2026-08-27 out-of-window test was recorded with Infineon's firmware
%    and RadarGUI, in Infineon's packet format. This reads it with the CARKIT
%    decoder in l2-sp (Carkit.readConfig, Carkit.readFrame, which use the
%    vendored Infineon DecodeConfig) and writes every frame as little-endian
%    int16 ADC counts in C order [chirp, sample, rx], with a JSON sidecar
%    holding the frame's mode, waveform, TX/RX configuration and SHA-256, plus
%    recording.json with the full decoded configuration. window_common.py
%    reads the result.
%
%    Carkit.readFrame returns the cube normalized to full scale (counts/2^11);
%    multiplying back gives the integers exactly, which is checked.
%
%    Needs l2-sp's Matlab code on the path (run addL2SpMatlabPath.m).
%
%  Usage:
%    window_convert_infineon
%    window_convert_infineon(source,target)

if nargin<1 || isempty(source)
    source = fullfile(getenv('HOME'),'Data','carkit',...
        '2026-08-27_test_out_of_office_window','2026_08_27_16_24_27_adc');
end
if nargin<2 || isempty(target)
    target = fullfile(fileparts(source),'converted_adc');
end

ADC_FULL_SCALE = 2^11;

[operConfig,sigParam] = Carkit.readConfig(source);
files = Carkit.frameFiles(source);
if ~isfolder(target)
    mkdir(target);
end

l2spRoot = getL2SpRoot;
[~,commit] = system(sprintf('git -C "%s" rev-parse HEAD',l2spRoot));
recording = struct(...
    'description',['Offline conversion of a CARKIT RadarGUI raw ADC ' ...
    'recording (Infineon firmware), one file pair per frame'],...
    'source_folder',source,...
    'source_config_sha256',sha256(fullfile(source,'config.bin')),...
    'converter','studies/2026-09-11_carkit-validation/window_convert_infineon.m',...
    'decoder','l2-sp matlab/Radars/+Carkit (Carkit.readConfig, Carkit.readFrame)',...
    'l2sp_commit',strtrim(commit),...
    'matlab_version',version,...
    'converted_utc',char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss''Z''')),...
    'frames',numel(files),...
    'operation_config',operConfig,...
    'signal_processing_parameters',sigParam);
writeJson(fullfile(target,'recording.json'),recording);

for k = 1:numel(files)
    frame = Carkit.readFrame(files{k},operConfig,sigParam);
    counts = frame.cube * ADC_FULL_SCALE;
    if any(counts(:)~=round(counts(:)))
        error('window_convert_infineon:NotInteger',...
            '%s does not scale back to integer ADC counts',files{k});
    end
    % samples by rx by ramp -> rx fastest, then sample, then ramp (C order
    % [ramp, sample, rx])
    counts = int16(permute(counts,[2 1 3]));
    name = sprintf('frame_%04d',k-1);
    binFile = fullfile(target,[name '.bin']);
    fid = fopen(binFile,'w','ieee-le');
    fwrite(fid,counts,'int16');
    fclose(fid);

    mc = operConfig.modeConfig(frame.mode+1);
    wc = mc.waveformConfig(frame.waveform+1);
    sidecar = struct(...
        'file',[name '.bin'],...
        'index',k-1,...
        'source_file',files{k}(numel(source)+2:end),...
        'frame_no',double(frame.frame_no),...
        'time_stamp_ms',double(frame.time_stamp),...
        'mode',frame.mode,...
        'waveform',frame.waveform,...
        'shape',[size(counts,3) size(counts,2) size(counts,1)],...
        'axes',{{'chirp','sample','rx'}},...
        'dtype','<i2',...
        'units','ADC counts',...
        'mode_config',rmfield(mc,{'waveformConfig','rxConfig','txConfig'}),...
        'waveform_config',wc,...
        'tx_config',mc.txConfig(frame.waveform+1),...
        'rx_config',mc.rxConfig(frame.waveform+1),...
        'params',frame.params,...
        'status',frame.status.system,...
        'sha256',sha256(binFile));
    writeJson(fullfile(target,[name '.json']),sidecar);
end

fprintf('Wrote %d frames to %s\n',numel(files),target);

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

function writeJson(filename,value)

fid = fopen(filename,'w');
fprintf(fid,'%s\n',jsonencode(value,'PrettyPrint',true));
fclose(fid);

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

function digest = sha256(filename)

fid = fopen(filename,'r');
bytes = fread(fid,Inf,'*uint8');
fclose(fid);
md = java.security.MessageDigest.getInstance('SHA-256');
md.update(bytes);
digest = lower(reshape(dec2hex(typecast(md.digest(),'uint8'),2).',1,[]));
