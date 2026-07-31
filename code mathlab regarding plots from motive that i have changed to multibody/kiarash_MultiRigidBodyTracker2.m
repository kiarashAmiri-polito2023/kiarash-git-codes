function MultiRigidBodyTracker()
% MULTIRIGIDBODYTRACKER  Scalable multi-Rigid-Body live tracking, plotting,
% and logging framework for OptiTrack Motive via the NatNet MATLAB client.
%
% WHY THIS EXISTS
%   The stock OptiTrack samples (NatNetPollingSample.m, NatNetEventHandlerSample.m)
%   hardcode a single Rigid Body and identify it by array index
%   (data.RigidBodies(1)). That breaks the moment Motive streams Rigid
%   Bodies in a different order, or you add/rename one. This script fixes
%   that by identifying every Rigid Body by its NatNet streaming ID
%   (looked up once from the model description), never by array position.
%
% WHAT IT DOES
%   1. Connects to Motive through natnet.m
%   2. Reads the model description ONCE to build an ID -> Name map
%   3. Each frame, dynamically loops over however many Rigid Bodies are
%      present (no fixed count, no RigidBodies(1)/(2)/(3))
%   4. Asks you, one Rigid Body at a time and in order, whether to
%      record it at all -- answering "no" fully excludes it from BOTH
%      plotting AND the Data struct/.mat file (useful for skipping a
%      "Ground_RB" reference body Motive has enabled but you don't need,
%      keeping data volume down)
%   5. Auto-generates 2 subplots (Position, Orientation) per Rigid Body
%      you answered "yes" to
%   6. Logs every frame into Data.<RigidBodyName>.Time / .Position /
%      .Orientation.Quaternion / .Orientation.Euler -- ONLY for the
%      Rigid Bodies you answered "yes" to
%   7. Saves everything to a timestamped .mat file when you close the figure
%
% REQUIREMENTS
%   - OptiTrack Motive 2.0+, NatNet 3.0+ streaming enabled
%   - natnet.m (or natnet.p) on the MATLAB path
%   - Rigid Body Data streaming must be enabled in Motive's
%     Data Streaming pane (Stream Options -> Stream Rigid Bodies = True)
%
% USAGE
%   1. In Motive: make sure your Rigid Bodies (e.g. Helmet_RB,
%      LeftWrist_RB, RightWrist_RB) are created and visible, and Live
%      mode / Broadcast Frame Data is on.
%   2. Run this file. A docked figure opens with live plots.
%   3. Close the figure (or Ctrl+C) to stop and auto-save the session.
%
% IMPORTANT ONE-TIME CHECK BEFORE YOUR FIRST REAL SESSION
%   This code assumes both model.RigidBody(i) and frame.RigidBodies(k)
%   expose an .ID field (the NatNet streaming ID), which is the standard
%   NatNet convention used to match definitions to live samples. If your
%   installed natnet.m version names this field differently, run:
%       natnetclient = natnet; natnetclient.connect;
%       frame = natnetclient.getFrame; disp(frame.RigidBodies(1))
%   once and confirm the field name, then adjust getRigidBodyID() below
%   if needed (it's isolated in one place for exactly this reason).

    fprintf('Multi-Rigid-Body NatNet Tracker - Start\n');
    fprintf('=========================================================\n');

    %% 1. NatNet initialization
    natnetclient = connectToNatNet();

    %% 2. Rigid Body identification (ID -> Name map, built once)
    [idToName, rbNames] = buildRigidBodyMap(natnetclient);
    numRB = numel(rbNames);
    fprintf('Detected %d Rigid Body/Bodies from Motive:\n', numRB);
    for i = 1:numRB
        fprintf('   - %s\n', rbNames{i});
    end

    %% 3. Ask, one by one and in order, which Rigid Bodies to record
    %  Anything answered "no" here is fully excluded from BOTH the live
    %  plots AND the Data struct/.mat file -- it is never logged, so it
    %  never adds to data volume. This is a deliberate change from an
    %  earlier version that logged everything regardless of the answer.
    selectedNames = selectRigidBodiesToRecord(rbNames);

    %% 4. Real-time data storage (struct-of-structs, one field per RB name)
    %  Built ONLY from selectedNames -- a Rigid Body you said "no" to
    %  has no field in Data at all, so nothing about it is ever written.
    Data = initializeDataStorage(selectedNames);

    %% 5. Dynamic plot generation (2 subplots per SELECTED Rigid Body)
    [figHandle, plotHandles] = initializePlots(selectedNames);

    %% 6. Receive Frame loop + Data Update + Plot Update
    fprintf('\nStreaming... close the figure window to stop and save.\n\n');
    startTime = tic;
while ishandle(figHandle)

    frame = natnetclient.getFrame;

    if isempty(frame) || isempty(frame.RigidBodies)
        pause(0.001);
        continue;
    end

    % ============================================================
    % DEBUG INFORMATION
    % ============================================================

    fprintf('\n========================================\n');

    if isfield(frame,'iFrame')
        fprintf('Frame Number : %d\n', frame.iFrame);
    else
        fprintf('Frame Number : UNKNOWN\n');
    end

    fprintf('Rigid Bodies received : %d\n', numel(frame.RigidBodies));

    fprintf('========================================\n');

    t = toc(startTime);

    % Dynamically loop over however many Rigid Bodies are in THIS frame
    for k = 1:numel(frame.RigidBodies)

        rb = frame.RigidBodies(k);

        fprintf('\n----------- Rigid Body %d -----------\n',k);

        fprintf('Streaming ID : %d\n',rb.ID);

        fprintf('Position (m) : %.4f %.4f %.4f\n', ...
                rb.x,rb.y,rb.z);

        fprintf('Quaternion   : %.4f %.4f %.4f %.4f\n', ...
                rb.qx,rb.qy,rb.qz,rb.qw);

        rbID = getRigidBodyID(rb);

        if ~isKey(idToName, rbID)

            fprintf('WARNING : Unknown ID (%d)\n',rbID);

            [idToName, ~] = buildRigidBodyMap(natnetclient);

            continue

        end

        name = idToName(rbID);

        fprintf('Resolved Name : %s\n',name);

        fieldName = matlab.lang.makeValidName(name);

        if ~isfield(Data, fieldName)

            fprintf('Skipped (User selected NO)\n');

            continue

        end

        fprintf('Recording : %s\n',fieldName);

        [roll, pitch, yaw] = quaternionToEuler( ...
            double(rb.qx), ...
            double(rb.qy), ...
            double(rb.qz), ...
            double(rb.qw));

        positionMM = double([rb.x rb.y rb.z])*1000;

        Data.(fieldName).Time(end+1) = t;
        Data.(fieldName).Position(end+1,:) = positionMM;
        Data.(fieldName).Orientation.Quaternion(end+1,:) = ...
            double([rb.qx rb.qy rb.qz rb.qw]);

        Data.(fieldName).Orientation.Euler(end+1,:) = ...
            [roll pitch yaw];

        if isfield(plotHandles,fieldName)

            fprintf('Updating Plot : %s\n',fieldName);

            updatePlots( ...
                plotHandles.(fieldName), ...
                t, ...
                positionMM, ...
                [roll pitch yaw]);

        end

    end

    drawnow limitrate;

end
   

            if ~isKey(idToName, rbID)
                % Not one of the Rigid Bodies detected at startup (e.g. a
                % brand new asset created in Motive mid-session). Since
                % you were never asked about it, it is treated as
                % excluded by default -- refresh the map just so future
                % frames resolve its name correctly if you rerun with it
                % included, but do NOT record or plot it now.
                [idToName, ~] = buildRigidBodyMap(natnetclient);
                continue
            end

            name = idToName(rbID);
            fieldName = matlab.lang.makeValidName(name);

            if ~isfield(Data, fieldName)
                % You answered "no" for this one -- skip entirely, no
                % logging, no plotting, exactly as requested.
                continue
            end

            [roll, pitch, yaw] = quaternionToEuler(double(rb.qx), double(rb.qy), double(rb.qz), double(rb.qw));
            positionMM = double([rb.x, rb.y, rb.z]) * 1000; % NatNet gives meters, often as single

            Data.(fieldName).Time(end+1)                    = t;
            Data.(fieldName).Position(end+1, :)             = positionMM;
            Data.(fieldName).Orientation.Quaternion(end+1,:) = double([rb.qx, rb.qy, rb.qz, rb.qw]);
            Data.(fieldName).Orientation.Euler(end+1, :)     = [roll, pitch, yaw];

            if isfield(plotHandles, fieldName)
                updatePlots(plotHandles.(fieldName), t, positionMM, [roll, pitch, yaw]);
            end
        end

        drawnow limitrate;
    end

    %% 7. Cleanup and save
    fprintf('=========================================================\n');
    fprintf('Figure closed - disconnecting and saving session data.\n');
    natnetclient.disconnect;

    fileName = ['MocapSession_' datestr(now, 'yyyymmdd_HHMMSS') '.mat'];
    save(fileName, 'Data');
    fprintf('Saved: %s\n', fileName);
    fprintf('Multi-Rigid-Body NatNet Tracker - End\n');
end


%% ------------------------------------------------------------------
%  LOCAL FUNCTIONS
%  (kept in this one file, no globals, so the whole tool is portable --
%  copy this single .m file anywhere natnet.m is on the path)
%  ------------------------------------------------------------------

function natnetclient = connectToNatNet()
    fprintf('Creating natnet client object\n');
    natnetclient = natnet;

    % Change these two if Motive runs on a different PC than MATLAB
    natnetclient.HostIP = '127.0.0.1';
    natnetclient.ClientIP = '127.0.0.1';
    natnetclient.ConnectionType = 'Multicast';
    natnetclient.connect;

    if natnetclient.IsConnected == 0
        error(['Client failed to connect. Make sure Motive is running, ' ...
               'Broadcast Frame Data is enabled in the Data Streaming ' ...
               'pane, and the Host/Client IP addresses are correct.']);
    end
    fprintf('Connected to Motive.\n');
end


function [idToName, rbNames] = buildRigidBodyMap(natnetclient)
% Builds a streaming-ID -> Name lookup from the model description.
% This is the ONLY place identity comes from array order at all (the
% model description itself), and even here we immediately convert it
% into an ID-keyed map so nothing downstream ever depends on order again.

    model = natnetclient.getModelDescription;
    if model.RigidBodyCount < 1
        error(['No Rigid Bodies found in Motive. Create at least one ' ...
               'Rigid Body asset (e.g. from your helmet/wristband markers) ' ...
               'and make sure it is visible before running this script.']);
    end

    idToName = containers.Map('KeyType', 'double', 'ValueType', 'char');
    rbNames = cell(1, model.RigidBodyCount);

    for i = 1:model.RigidBodyCount
        rbID   = model.RigidBody(i).ID;
        rbName = model.RigidBody(i).Name;
        idToName(rbID) = rbName;
        rbNames{i} = rbName;
    end
end


function selectedNames = selectRigidBodiesToRecord(rbNames)
% Interactively asks, ONE Rigid Body at a time and IN ORDER (same order
% Motive/buildRigidBodyMap detected them), whether to record it at all.
%
% Answering "no" fully excludes that Rigid Body from BOTH the live plots
% AND the Data struct/.mat file -- nothing about it is stored, so it
% never adds to your data volume. Use this to skip things like a
% "Ground_RB" reference body that Motive has enabled but you have no use
% for in your dataset.
%
% Accepted as YES: any answer starting with 'y' or 'Y' (yes/Yes/y...).
% Anything else, including an empty Enter press, counts as NO.

    fprintf('\n--- Select which Rigid Bodies to record ---\n');
    fprintf('(Anything you answer "no" to will NOT be logged or plotted.)\n\n');

    selectedNames = {};
    for i = 1:numel(rbNames)
        prompt = sprintf('Record "%s"? (yes/no): ', rbNames{i});
        answer = input(prompt, 's');
        if ~isempty(answer) && strcmpi(answer(1), 'y')
            selectedNames{end+1} = rbNames{i}; %#ok<AGROW>
        end
    end

    fprintf('\nWill be recorded and plotted: ');
    if isempty(selectedNames)
        fprintf('(none)\n');
    else
        fprintf('%s\n', strjoin(selectedNames, ', '));
    end
    fprintf('--------------------------------------------\n\n');
end


function rbID = getRigidBodyID(rb)
% Isolated in its own function on purpose: if your natnet.m version
% names the streaming-ID field differently than ".ID", this is the only
% line you need to change.
    rbID = rb.ID;
end


function Data = initializeDataStorage(rbNames)
    Data = struct();
    for i = 1:numel(rbNames)
        fieldName = matlab.lang.makeValidName(rbNames{i});
        Data.(fieldName) = newRigidBodyRecord();
    end
end


function record = newRigidBodyRecord()
    record.Time = [];
    record.Position = zeros(0, 3);                  % [X Y Z] in mm
    record.Orientation.Quaternion = zeros(0, 4);     % [qx qy qz qw]
    record.Orientation.Euler = zeros(0, 3);          % [Roll Pitch Yaw] in degrees
end


function [figHandle, plotHandles] = initializePlots(rbNames)
    numRB = numel(rbNames);

    figHandle = figure('Name', 'Multi-Rigid-Body Tracking', ...
                        'WindowStyle', 'docked');

    plotHandles = struct();

    if numRB == 0
        % User said "no" to every Rigid Body -- keep the window open
        % (so the main loop's ishandle() check still works to let you
        % stop the session) but make it obvious nothing is being plotted.
        axis off;
        text(0.5, 0.5, 'No Rigid Bodies selected for plotting.', ...
             'HorizontalAlignment', 'center', 'FontSize', 12);
        text(0.5, 0.4, 'Data is still being logged. Close this window to stop.', ...
             'HorizontalAlignment', 'center', 'FontSize', 10, 'Color', [0.4 0.4 0.4]);
        return;
    end

    for i = 1:numRB
        fieldName = matlab.lang.makeValidName(rbNames{i});
        displayName = strrep(rbNames{i}, '_', '\_'); % escape for plot titles

        % --- Position subplot (left column) ---
        subplot(numRB, 2, 2*i - 1);
        title([displayName ' - Position']);
        xlabel('Time (s)'); ylabel('Position (mm)');
        hold on; grid on;
        hX = animatedline('Color', [1 0 0], 'DisplayName', 'X');
        hY = animatedline('Color', [0 1 0], 'DisplayName', 'Y');
        hZ = animatedline('Color', [0 0 1], 'DisplayName', 'Z');
        legend('show', 'Location', 'best');

        % --- Orientation subplot (right column) ---
        subplot(numRB, 2, 2*i);
        title([displayName ' - Orientation']);
        xlabel('Time (s)'); ylabel('Angle (deg)');
        hold on; grid on;
        hRoll  = animatedline('Color', [1 0 0], 'DisplayName', 'Roll');
        hPitch = animatedline('Color', [0 1 0], 'DisplayName', 'Pitch');
        hYaw   = animatedline('Color', [0 0 1], 'DisplayName', 'Yaw');
        legend('show', 'Location', 'best');

        plotHandles.(fieldName) = struct( ...
            'X', hX, 'Y', hY, 'Z', hZ, ...
            'Roll', hRoll, 'Pitch', hPitch, 'Yaw', hYaw);
    end
end


function updatePlots(h, t, positionMM, eulerDeg)
    addpoints(h.X, t, positionMM(1));
    addpoints(h.Y, t, positionMM(2));
    addpoints(h.Z, t, positionMM(3));

    addpoints(h.Roll,  t, eulerDeg(1));
    addpoints(h.Pitch, t, eulerDeg(2));
    addpoints(h.Yaw,   t, eulerDeg(3));
end


function [rollDeg, pitchDeg, yawDeg] = quaternionToEuler(qx, qy, qz, qw)
% Converts a NatNet quaternion to Roll/Pitch/Yaw in degrees.
% Standard ZYX (aerospace) convention.

    sinr_cosp = 2 * (qw*qx + qy*qz);
    cosr_cosp = 1 - 2 * (qx*qx + qy*qy);
    roll = atan2(sinr_cosp, cosr_cosp);

    sinp = 2 * (qw*qy - qz*qx);
    if abs(sinp) >= 1
        pitch = sign(sinp) * (pi/2); % gimbal lock guard
    else
        pitch = asin(sinp);
    end

    siny_cosp = 2 * (qw*qz + qx*qy);
    cosy_cosp = 1 - 2 * (qy*qy + qz*qz);
    yaw = atan2(siny_cosp, cosy_cosp);

    rollDeg  = rad2deg(roll);
    pitchDeg = rad2deg(pitch);
    yawDeg   = rad2deg(yaw);
end
