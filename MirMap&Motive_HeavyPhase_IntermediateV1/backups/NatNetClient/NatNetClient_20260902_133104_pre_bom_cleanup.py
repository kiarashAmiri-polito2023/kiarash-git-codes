#Copyright © 2018 Naturalpoint
#
#Licensed under the Apache License, Version 2.0 (the "License")
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.

import socket
import struct
from threading import Thread
import copy
import time
import DataDescriptions
import MoCapData

def trace( *args ):
    print( "".join(map(str,args)) )

def trace_dd( *args ):
    pass

def trace_mf( *args ):
    pass

def get_message_id(data):
    message_id = int.from_bytes( data[0:2], byteorder='little' )
    return message_id

Vector2 = struct.Struct( '<ff' )
Vector3 = struct.Struct( '<fff' )
Quaternion = struct.Struct( '<ffff' )
FloatValue = struct.Struct( '<f' )
DoubleValue = struct.Struct( '<d' )
NNIntValue = struct.Struct( '<I')
FPCalMatrixRow = struct.Struct( '<ffffffffffff' )
FPCorners      = struct.Struct( '<ffffffffffff')

class NatNetClient:
    print_level = 20
    
    def __init__( self ):
        self.server_ip_address = "127.0.0.1"
        self.local_ip_address = "127.0.0.1"
        self.multicast_address = "239.255.42.99"
        self.command_port = 1510
        self.data_port = 1511
        self.use_multicast = True

        self.rigid_body_listener = None
        self.new_frame_listener  = None
        self.model_def_listener  = None  # درگاه ارتباطی نام‌های موتیو

        self.__application_name = "Not Set"
        self.__nat_net_stream_version_server = [0,0,0,0]
        self.__nat_net_requested_version = [0,0,0,0]
        self.__server_version = [0,0,0,0]
        self.__is_locked = False
        self.__can_change_bitstream_version = False

        self.command_thread = None
        self.data_thread = None
        self.command_socket = None
        self.data_socket = None
        self.stop_threads = False

    NAT_CONNECT               = 0
    NAT_SERVERINFO            = 1
    NAT_REQUEST               = 2
    NAT_RESPONSE              = 3
    NAT_REQUEST_MODELDEF      = 4
    NAT_MODELDEF              = 5
    NAT_REQUEST_FRAMEOFDATA   = 6
    NAT_FRAMEOFDATA           = 7
    NAT_MESSAGESTRING         = 8
    NAT_DISCONNECT            = 9
    NAT_KEEPALIVE             = 10
    NAT_UNRECOGNIZED_REQUEST  = 100
    NAT_UNDEFINED             = 999999.9999

    def set_client_address(self, local_ip_address):
        if not self.__is_locked:
            self.local_ip_address = local_ip_address

    def get_client_address(self):
        return self.local_ip_address

    def set_server_address(self,server_ip_address):
        if not self.__is_locked:
            self.server_ip_address = server_ip_address

    def get_server_address(self):
        return self.server_ip_address

    def set_use_multicast(self, use_multicast):
        if not self.__is_locked:
            self.use_multicast = use_multicast

    def can_change_bitstream_version(self):
        return self.__can_change_bitstream_version

    def set_nat_net_version(self, major, minor):
        return_code = -1
        if self.__can_change_bitstream_version and \
            (major != self.__nat_net_requested_version[0]) and\
            (minor != self.__nat_net_requested_version[1]):
            sz_command = "Bitstream,%1.1d.%1.1d"%(major, minor)
            return_code = self.send_command(sz_command)
            if return_code >=0:
                self.__nat_net_requested_version[0] = major
                self.__nat_net_requested_version[1] = minor
                self.__nat_net_requested_version[2] = 0
                self.__nat_net_requested_version[3] = 0
                self.send_command("TimelinePlay")
                time.sleep(0.1)
                tmpCommands=["TimelinePlay", "TimelineStop", "SetPlaybackCurrentFrame,0", "TimelineStop"]
                self.send_commands(tmpCommands, False)
                time.sleep(2)
        return return_code

    def get_major(self):
        return self.__nat_net_requested_version[0]

    def get_minor(self):
        return self.__nat_net_requested_version[1]

    def set_print_level(self, print_level=0):
        if(print_level >=0):
            self.print_level = print_level
        return self.print_level

    def get_print_level(self):
        return self.print_level

    def connected(self):
        ret_value = True
        if self.command_socket == None:
            ret_value = False
        elif self.data_socket == None:
            ret_value = False
        elif self.get_application_name() == "Not Set":
            ret_value = False
        elif (self.__server_version[0] == 0) and (self.__server_version[1] == 0):
            ret_value = False
        return ret_value

    def __create_command_socket( self ):
        result = None
        if self.use_multicast :
            result = socket.socket( socket.AF_INET, socket.SOCK_DGRAM, 0 )
            result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                result.bind( ('', 0) )
            except socket.error:
                result = None
            result.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            result.settimeout(2.0)
        else:
            result = socket.socket( socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            try:
                result.bind( (self.local_ip_address, 0) )
            except socket.error:
                result = None
            result.settimeout(2.0)
            result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return result

    def __create_data_socket( self, port ):
        result = None
        if self.use_multicast:
            result = socket.socket( socket.AF_INET, socket.SOCK_DGRAM, 0)
            result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            result.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(self.multicast_address) + socket.inet_aton(self.local_ip_address))
            try:
                result.bind( (self.local_ip_address, port) )
            except socket.error:
                result = None
        else:
            result = socket.socket( socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                result.bind( ('', 0) )
            except socket.error:
                result = None
            if(self.multicast_address != "255.255.255.255"):
                result.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(self.multicast_address) + socket.inet_aton(self.local_ip_address))
        return result

    def __unpack_rigid_body( self, data, major, minor, rb_num):
        offset = 0
        new_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        pos = Vector3.unpack( data[offset:offset+12] )
        offset += 12
        rot = Quaternion.unpack( data[offset:offset+16] )
        offset += 16
        rigid_body = MoCapData.RigidBody(new_id, pos, rot)

        if self.rigid_body_listener is not None:
            self.rigid_body_listener( new_id, pos, rot )

        if major >= 2 :
            marker_error, = FloatValue.unpack( data[offset:offset+4] )
            offset += 4
            rigid_body.error = marker_error

        if ( ( major == 2 ) and ( minor >= 6 ) ) or major > 2 :
            param, = struct.unpack( 'h', data[offset:offset+2] )
            tracking_valid = ( param & 0x01 ) != 0
            offset += 2
            rigid_body.tracking_valid = tracking_valid

        return offset, rigid_body

    def __unpack_skeleton( self, data, major, minor):
        offset = 0
        new_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        skeleton = MoCapData.Skeleton(new_id)
        rigid_body_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        for rb_num in range( 0, rigid_body_count ):
            offset_tmp, rigid_body = self.__unpack_rigid_body( data[offset:], major, minor, rb_num )
            skeleton.add_rigid_body(rigid_body)
            offset+=offset_tmp
        return offset, skeleton

    def __unpack_frame_prefix_data( self, data):
        offset = 0
        frame_number = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        frame_prefix_data=MoCapData.FramePrefixData(frame_number)
        return offset, frame_prefix_data

    def __unpack_marker_set_data( self, data, packet_size, major, minor):
        marker_set_data=MoCapData.MarkerSetData()
        offset = 0
        marker_set_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        for i in range( 0, marker_set_count ):
            marker_data = MoCapData.MarkerData()
            model_name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( model_name ) + 1
            marker_data.set_model_name(model_name)
            marker_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            for j in range( 0, marker_count ):
                pos = Vector3.unpack( data[offset:offset+12] )
                offset += 12
                marker_data.add_pos(pos)
            marker_set_data.add_marker_data(marker_data)
        unlabeled_markers_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        for i in range( 0, unlabeled_markers_count ):
            pos = Vector3.unpack( data[offset:offset+12] )
            offset += 12
            marker_set_data.add_unlabeled_marker(pos)
        return offset, marker_set_data

    def __unpack_rigid_body_data( self, data, packet_size, major, minor):
        rigid_body_data = MoCapData.RigidBodyData()
        offset = 0
        rigid_body_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        for i in range( 0, rigid_body_count ):
            offset_tmp, rigid_body = self.__unpack_rigid_body( data[offset:], major, minor, i )
            offset += offset_tmp
            rigid_body_data.add_rigid_body(rigid_body)
        return offset, rigid_body_data

    def __unpack_skeleton_data( self, data, packet_size, major, minor):
        skeleton_data = MoCapData.SkeletonData()
        offset = 0
        skeleton_count = 0
        if( ( major == 2 and minor > 0 ) or major > 2 ):
            skeleton_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            for _ in range( 0, skeleton_count ):
                rel_offset, skeleton = self.__unpack_skeleton( data[offset:], major, minor )
                offset += rel_offset
                skeleton_data.add_skeleton(skeleton)
        return offset, skeleton_data

    def __decode_marker_id(self, new_id):
        model_id = new_id >> 16
        marker_id = new_id & 0x0000ffff
        return model_id, marker_id

    def __unpack_labeled_marker_data( self, data, packet_size, major, minor):
        labeled_marker_data = MoCapData.LabeledMarkerData()
        offset = 0
        labeled_marker_count = 0
        if( ( major == 2 and minor > 3 ) or major > 2 ):
            labeled_marker_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            for _ in range( 0, labeled_marker_count ):
                tmp_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4
                model_id, marker_id = self.__decode_marker_id(tmp_id)
                pos = Vector3.unpack( data[offset:offset+12] )
                offset += 12
                size = FloatValue.unpack( data[offset:offset+4] )
                offset += 4
                param = 0
                if( ( major == 2 and minor >= 6 ) or major > 2):
                    param, = struct.unpack( 'h', data[offset:offset+2] )
                    offset += 2
                residual = 0.0
                if major >= 3 :
                    residual, = FloatValue.unpack( data[offset:offset+4] )
                    offset += 4
                labeled_marker = MoCapData.LabeledMarker(tmp_id, pos, size, param, residual)
                labeled_marker_data.add_labeled_marker(labeled_marker)
        return offset, labeled_marker_data

    def __unpack_force_plate_data( self, data, packet_size, major, minor):
        force_plate_data = MoCapData.ForcePlateData()
        offset = 0
        force_plate_count = 0
        if( ( major == 2 and minor >= 9 ) or major > 2 ):
            force_plate_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            for i in range( 0, force_plate_count ):
                force_plate_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4
                force_plate = MoCapData.ForcePlate(force_plate_id)
                force_plate_channel_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4
                for j in range( force_plate_channel_count ):
                    fp_channel_data = MoCapData.ForcePlateChannelData()
                    force_plate_channel_frame_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
                    offset += 4
                    for k in range( force_plate_channel_frame_count ):
                        force_plate_channel_val = FloatValue.unpack( data[offset:offset+4] )
                        offset += 4
                        fp_channel_data.add_frame_entry(force_plate_channel_val)
                    force_plate.add_channel_data(fp_channel_data)
                force_plate_data.add_force_plate(force_plate)
        return offset, force_plate_data

    def __unpack_device_data( self, data, packet_size, major, minor):
        device_data = MoCapData.DeviceData()
        offset = 0
        device_count = 0
        if ( major == 2 and minor >= 11 ) or (major > 2) :
            device_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            for i in range( 0, device_count ):
                device_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4
                device = MoCapData.Device(device_id)
                device_channel_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4
                for j in range( 0, device_channel_count ):
                    device_channel_data = MoCapData.DeviceChannelData()
                    device_channel_frame_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
                    offset += 4
                    for k in range( 0, device_channel_frame_count ):
                        device_channel_val = FloatValue.unpack( data[offset:offset+4] )
                        offset += 4
                        device_channel_data.add_frame_entry(device_channel_val)
                    device.add_channel_data(device_channel_data)
                device_data.add_device(device)
        return offset, device_data

    def __unpack_frame_suffix_data( self, data, packet_size, major, minor):
        frame_suffix_data = MoCapData.FrameSuffixData()
        offset = 0
        timecode = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        frame_suffix_data.timecode = timecode
        timecode_sub = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        frame_suffix_data.timecode_sub = timecode_sub

        if ( major == 2 and minor >= 7 ) or (major > 2 ):
            timestamp, = DoubleValue.unpack( data[offset:offset+8] )
            offset += 8
        else:
            timestamp, = FloatValue.unpack( data[offset:offset+4] )
            offset += 4
        frame_suffix_data.timestamp = timestamp

        if major >= 3 :
            stamp_camera_mid_exposure = int.from_bytes( data[offset:offset+8], byteorder='little' )
            offset += 8
            frame_suffix_data.stamp_camera_mid_exposure = stamp_camera_mid_exposure
            stamp_data_received = int.from_bytes( data[offset:offset+8], byteorder='little' )
            offset += 8
            frame_suffix_data.stamp_data_received = stamp_data_received
            stamp_transmit = int.from_bytes( data[offset:offset+8], byteorder='little' )
            offset += 8
            frame_suffix_data.stamp_transmit = stamp_transmit

        param, = struct.unpack( 'h', data[offset:offset+2] )
        is_recording = ( param & 0x01 ) != 0
        tracked_models_changed = ( param & 0x02 ) != 0
        offset += 2
        frame_suffix_data.param = param
        frame_suffix_data.is_recording = is_recording
        frame_suffix_data.tracked_models_changed = tracked_models_changed

        return offset, frame_suffix_data

    def __unpack_mocap_data( self, data : bytes, packet_size, major, minor):
        mocap_data = MoCapData.MoCapData()
        data = memoryview( data )
        offset = 0
        rel_offset = 0

        rel_offset, frame_prefix_data = self.__unpack_frame_prefix_data(data[offset:])
        offset += rel_offset
        mocap_data.set_prefix_data(frame_prefix_data)
        frame_number = frame_prefix_data.frame_number

        rel_offset, marker_set_data = self.__unpack_marker_set_data(data[offset:], (packet_size - offset), major, minor)
        offset += rel_offset
        mocap_data.set_marker_set_data(marker_set_data)
        marker_set_count = marker_set_data.get_marker_set_count()
        unlabeled_markers_count = marker_set_data.get_unlabeled_marker_count()

        rel_offset, rigid_body_data = self.__unpack_rigid_body_data(data[offset:], (packet_size - offset), major, minor)
        offset += rel_offset
        mocap_data.set_rigid_body_data(rigid_body_data)
        rigid_body_count = rigid_body_data.get_rigid_body_count()

        rel_offset, skeleton_data = self.__unpack_skeleton_data(data[offset:], (packet_size - offset), major, minor)
        offset += rel_offset
        mocap_data.set_skeleton_data(skeleton_data)
        skeleton_count = skeleton_data.get_skeleton_count()

        rel_offset, labeled_marker_data = self.__unpack_labeled_marker_data(data[offset:], (packet_size - offset), major, minor)
        offset += rel_offset
        mocap_data.set_labeled_marker_data(labeled_marker_data)
        labeled_marker_count = labeled_marker_data.get_labeled_marker_count()

        rel_offset, force_plate_data = self.__unpack_force_plate_data(data[offset:], (packet_size - offset), major, minor)
        offset += rel_offset
        mocap_data.set_force_plate_data(force_plate_data)

        rel_offset, device_data = self.__unpack_device_data(data[offset:], (packet_size - offset), major, minor)
        offset += rel_offset
        mocap_data.set_device_data(device_data)

        rel_offset, frame_suffix_data = self.__unpack_frame_suffix_data(data[offset:], (packet_size - offset), major, minor)
        offset += rel_offset
        mocap_data.set_suffix_data(frame_suffix_data)

        timecode = frame_suffix_data.timecode
        timecode_sub = frame_suffix_data.timecode_sub
        timestamp = frame_suffix_data.timestamp
        is_recording = frame_suffix_data.is_recording
        tracked_models_changed = frame_suffix_data.tracked_models_changed

        if self.new_frame_listener is not None:
            data_dict = {}
            data_dict["frame_number"] = frame_number
            data_dict["marker_set_count"] = marker_set_count
            data_dict["unlabeled_markers_count"] = unlabeled_markers_count
            data_dict["rigid_body_count"] = rigid_body_count
            data_dict["skeleton_count"] = skeleton_count
            data_dict["labeled_marker_count"] = labeled_marker_count
            data_dict["timecode"] = timecode
            data_dict["timecode_sub"] = timecode_sub
            data_dict["timestamp"] = timestamp
            data_dict["is_recording"] = is_recording
            data_dict["tracked_models_changed"] = tracked_models_changed
            self.new_frame_listener( data_dict )

        return offset, mocap_data

    def __unpack_marker_set_description( self, data, major, minor):
        ms_desc = DataDescriptions.MarkerSetDescription()
        offset = 0
        name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
        offset += len( name ) + 1
        ms_desc.set_name(name)
        marker_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        for i in range( 0, marker_count ):
            name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( name ) + 1
            ms_desc.add_marker_name(name)
        return offset, ms_desc

    def __unpack_rigid_body_description( self, data, major, minor):
        rb_desc = DataDescriptions.RigidBodyDescription()
        offset = 0
        if (major >= 2) or (major == 0):
            name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( name ) + 1
            rb_desc.set_name(name)
        new_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        rb_desc.set_id(new_id)
        parent_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        rb_desc.set_parent_id(parent_id)
        pos = Vector3.unpack( data[offset:offset+12] )
        offset += 12
        rb_desc.set_pos(pos[0],pos[1],pos[2])

        if (major >= 3) or (major == 0) :
            marker_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            marker_count_range = range( 0, marker_count )
            offset1 = offset
            offset2 = offset1 + (12*marker_count)
            offset3 = offset2 + (4*marker_count)
            marker_name = ""
            for marker in marker_count_range:
                marker_offset = Vector3.unpack(data[offset1:offset1+12])
                offset1 += 12
                active_label = int.from_bytes(data[offset2:offset2+4], byteorder = 'little')
                offset2 += 4
                if (major >= 4) or (major == 0):
                    marker_name, separator, remainder = bytes(data[offset3:]).partition( b'\0' )
                    marker_name = marker_name.decode( 'utf-8' )
                    offset3 += len( marker_name ) + 1
                rb_marker = DataDescriptions.RBMarker(marker_name, active_label, marker_offset)
                rb_desc.add_rb_marker(rb_marker)
            offset = offset3
        return offset, rb_desc

    def __unpack_skeleton_description( self, data, major, minor):
        skeleton_desc = DataDescriptions.SkeletonDescription()
        offset = 0
        name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
        offset += len( name ) + 1
        skeleton_desc.set_name(name)
        new_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        skeleton_desc.set_id(new_id)
        rigid_body_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        for i in range( 0, rigid_body_count ):
            offset_tmp, rb_desc_tmp = self.__unpack_rigid_body_description( data[offset:], major, minor )
            offset += offset_tmp
            skeleton_desc.add_rigid_body_description(rb_desc_tmp)
        return offset, skeleton_desc

    def __unpack_force_plate_description(self, data, major, minor):
        fp_desc = None
        offset = 0
        if major >= 3:
            fp_desc = DataDescriptions.ForcePlateDescription()
            new_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            fp_desc.set_id(new_id)
            serial_number, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( serial_number ) + 1
            fp_desc.set_serial_number(serial_number)
            f_width = FloatValue.unpack( data[offset:offset+4])
            offset += 4
            f_length = FloatValue.unpack( data[offset:offset+4])
            offset += 4
            fp_desc.set_dimensions(f_width[0], f_length[0])
            origin = Vector3.unpack( data[offset:offset+12] )
            offset += 12
            fp_desc.set_origin(origin[0],origin[1],origin[2])
            cal_matrix_tmp = [[0.0 for col in range(12)] for row in range(12)]
            for i in range(0,12):
                cal_matrix_row = FPCalMatrixRow.unpack(data[offset:offset+(12*4)])
                cal_matrix_tmp[i] = copy.deepcopy(cal_matrix_row)
                offset += (12*4)
            fp_desc.set_cal_matrix(cal_matrix_tmp)
            corners = FPCorners.unpack(data[offset:offset + (12*4)])
            offset += (12*4)
            o_2 = 0
            corners_tmp = [[0.0 for col in range(3)] for row in range(4)]
            for i in range(0,4):
                corners_tmp[i][0] = corners[o_2]
                corners_tmp[i][1] = corners[o_2+1]
                corners_tmp[i][2] = corners[o_2+2]
                o_2 += 3
            fp_desc.set_corners(corners_tmp)
            plate_type = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            fp_desc.set_plate_type(plate_type)
            channel_data_type = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            fp_desc.set_channel_data_type(channel_data_type)
            num_channels = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            for i in range(0, num_channels):
                channel_name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
                offset += len( channel_name ) + 1
                fp_desc.add_channel_name(channel_name)
        return offset, fp_desc

    def __unpack_device_description(self, data, major, minor):
        device_desc = None
        offset = 0
        if major >= 3:
            new_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( name ) + 1
            serial_number, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( serial_number ) + 1
            device_type = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            channel_data_type = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            device_desc = DataDescriptions.DeviceDescription(new_id, name, serial_number, device_type, channel_data_type)
            num_channels = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            for i in range(0, num_channels):
                channel_name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
                offset += len( channel_name ) + 1
                device_desc.add_channel_name(channel_name)
        return offset, device_desc

    def __unpack_camera_description(self, data, major, minor):
        offset = 0
        name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
        offset += len( name ) + 1
        position = Vector3.unpack( data[offset:offset+12] )
        offset += 12
        orientation = Quaternion.unpack( data[offset:offset+16] )
        offset += 16
        camera_desc = DataDescriptions.CameraDescription(name, position, orientation)
        return offset, camera_desc

    def __unpack_data_descriptions( self, data : bytes, packet_size, major, minor):
        data_descs = DataDescriptions.DataDescriptions()
        offset = 0
        dataset_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        for i in range( 0, dataset_count ):
            data_type = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            data_tmp = None
            if data_type == 0 :
                offset_tmp, data_tmp = self.__unpack_marker_set_description( data[offset:], major, minor )
            elif data_type == 1 :
                offset_tmp, data_tmp = self.__unpack_rigid_body_description( data[offset:], major, minor )
            elif data_type == 2 :
                offset_tmp, data_tmp = self.__unpack_skeleton_description( data[offset:], major, minor )
            elif data_type == 3 :
                offset_tmp, data_tmp = self.__unpack_force_plate_description(data[offset:], major, minor)
            elif data_type == 4 :
                offset_tmp, data_tmp = self.__unpack_device_description(data[offset:], major, minor)
            elif data_type == 5 :
                offset_tmp, data_tmp = self.__unpack_camera_description(data[offset:], major, minor)
            else:
                return offset
            offset += offset_tmp
            data_descs.add_data(data_tmp)
        return offset, data_descs

    def __unpack_server_info(self, data, packet_size, major, minor):
        offset = 0
        self.__application_name, separator, remainder = bytes(data[offset: offset+256]).partition( b'\0' )
        self.__application_name = str(self.__application_name, "utf-8")
        offset += 256
        server_version = struct.unpack( 'BBBB', data[offset:offset+4] )
        offset += 4
        self.__server_version[0] = server_version[0]
        self.__server_version[1] = server_version[1]
        self.__server_version[2] = server_version[2]
        self.__server_version[3] = server_version[3]
        nnsvs = struct.unpack( 'BBBB', data[offset:offset+4] )
        offset += 4
        self.__nat_net_stream_version_server[0] = nnsvs[0]
        self.__nat_net_stream_version_server[1] = nnsvs[1]
        self.__nat_net_stream_version_server[2] = nnsvs[2]
        self.__nat_net_stream_version_server[3] = nnsvs[3]
        if (self.__nat_net_requested_version[0] == 0) and (self.__nat_net_requested_version[1] == 0):
            self.__nat_net_requested_version[0] = self.__nat_net_stream_version_server[0]
            self.__nat_net_requested_version[1] = self.__nat_net_stream_version_server[1]
            self.__nat_net_requested_version[2] = self.__nat_net_stream_version_server[2]
            self.__nat_net_requested_version[3] = self.__nat_net_stream_version_server[3]
            if (self.__nat_net_stream_version_server[0] >= 4) and (self.use_multicast == False):
                self.__can_change_bitstream_version = True
        return offset

    def __command_thread_function( self, in_socket, stop, gprint_level):
        message_id_dict = {}
        if not self.use_multicast:
            in_socket.settimeout(2.0)
        data = bytearray(0)
        recv_buffer_size = 64*1024
        while not stop():
            try:
                data, addr = in_socket.recvfrom( recv_buffer_size )
            except socket.error:
                if stop():
                    pass
            except socket.timeout:
                pass

            if len( data ) > 0 :
                message_id = get_message_id(data)
                tmp_str = "mi_%1.1d"%message_id
                if tmp_str not in message_id_dict:
                    message_id_dict[tmp_str] = 0
                message_id_dict[tmp_str] += 1
                
                print_level = gprint_level()
                if message_id == self.NAT_FRAMEOFDATA:
                    if print_level > 0:
                        if (message_id_dict[tmp_str] % print_level) == 0:
                            print_level = 1
                        else:
                            print_level = 0
                message_id = self.__process_message( data , print_level)
                data = bytearray(0)

            if not self.use_multicast:
                if not stop():
                    self.send_keep_alive(in_socket, self.server_ip_address, self.command_port)
        return 0

    def __data_thread_function( self, in_socket, stop, gprint_level):
        message_id_dict = {}
        data = bytearray(0)
        recv_buffer_size = 64*1024
        while not stop():
            try:
                data, addr = in_socket.recvfrom( recv_buffer_size )
            except socket.error:
                if not stop():
                    return 1
            except socket.timeout:
                pass
            if len( data ) > 0 :
                message_id = get_message_id(data)
                tmp_str = "mi_%1.1d"%message_id
                if tmp_str not in message_id_dict:
                    message_id_dict[tmp_str] = 0
                message_id_dict[tmp_str] += 1
                
                print_level = gprint_level()
                if message_id == self.NAT_FRAMEOFDATA:
                    if print_level > 0:
                        if (message_id_dict[tmp_str] % print_level) == 0:
                            print_level = 1
                        else:
                            print_level = 0
                message_id = self.__process_message( data , print_level)
                data = bytearray(0)
        return 0

    def __process_message( self, data : bytes, print_level=0):
        major = self.get_major()
        minor = self.get_minor()
        message_id = get_message_id(data)
        packet_size = int.from_bytes( data[2:4], byteorder='little' )
        offset = 4

        if message_id == self.NAT_FRAMEOFDATA :
            offset_tmp, mocap_data = self.__unpack_mocap_data( data[offset:], packet_size, major, minor )
            offset += offset_tmp

        elif message_id == self.NAT_MODELDEF :
            offset_tmp, data_descs = self.__unpack_data_descriptions( data[offset:], packet_size, major, minor)
            offset += offset_tmp
            if self.model_def_listener is not None:
                self.model_def_listener(data_descs)

        elif message_id == self.NAT_SERVERINFO :
            offset += self.__unpack_server_info( data[offset:], packet_size, major, minor)

        elif message_id == self.NAT_RESPONSE :
            if packet_size == 4 :
                offset += 4

        return message_id

    def send_request( self, in_socket, command, command_str, address ):
        packet_size = 0
        if command == self.NAT_REQUEST_MODELDEF or command == self.NAT_REQUEST_FRAMEOFDATA :
            packet_size = 0
            command_str = ""
        elif command == self.NAT_REQUEST :
            packet_size = len( command_str ) + 1
        elif command == self.NAT_CONNECT :
            command_str = "Ping"
            packet_size = len( command_str ) + 1
        elif command == self.NAT_KEEPALIVE:
            packet_size = 0
            command_str = ""

        data = command.to_bytes( 2, byteorder='little' )
        data += packet_size.to_bytes( 2, byteorder='little' )
        data += command_str.encode( 'utf-8' )
        data += b'\0'
        return in_socket.sendto( data, address )

    def send_command( self, command_str):
        nTries = 3
        ret_val = -1
        while nTries:
            nTries -= 1
            ret_val = self.send_request( self.command_socket, self.NAT_REQUEST, command_str,  (self.server_ip_address, self.command_port) )
            if (ret_val != -1):
                break
        return ret_val

    def send_commands(self,tmpCommands, print_results: bool =True):
        for sz_command in tmpCommands:
            self.send_command(sz_command)

    def send_keep_alive(self,in_socket, server_ip_address, server_port):
        return self.send_request(in_socket, self.NAT_KEEPALIVE, "", (server_ip_address, server_port))

    def shutdown(self):
        self.stop_threads = True
        try:
            self.command_socket.close()
            self.data_socket.close()
            self.command_thread.join()
            self.data_thread.join()
        except Exception:
            pass

    def run( self ):
        self.data_socket = self.__create_data_socket( self.data_port )
        if self.data_socket is None :
            return False

        self.command_socket = self.__create_command_socket()
        if self.command_socket is None :
            return False
        self.__is_locked = True

        self.stop_threads = False
        self.data_thread = Thread( target = self.__data_thread_function, args = (self.data_socket, lambda : self.stop_threads, lambda : self.print_level, ))
        self.data_thread.start()

        self.command_thread = Thread( target = self.__command_thread_function, args = (self.command_socket, lambda : self.stop_threads, lambda : self.print_level,))
        self.command_thread.start()

        self.send_request(self.command_socket, self.NAT_CONNECT, "",  (self.server_ip_address, self.command_port) )
        return True