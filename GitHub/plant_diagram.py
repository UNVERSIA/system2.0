import plotly.graph_objects as go
import numpy as np

class PlantDiagramEngine:
    def __init__(self, unit_data):
        self.unit_data = unit_data
        self.unit_coords = self._initialize_coordinates()
        self.connections = self._initialize_connections()
        self.flow_particles = {}  # 存储水流粒子状态

    def _initialize_coordinates(self):
        """定义工艺单元坐标，依据PDF图纸布局"""
        return {
            # 预处理区（顶部横向排列）
            "粗格栅": {"x": 100, "y": 100, "width": 120, "height": 80, "area": "预处理区"},
            "提升泵房": {"x": 250, "y": 100, "width": 120, "height": 80, "area": "预处理区"},
            "细格栅": {"x": 400, "y": 100, "width": 120, "height": 80, "area": "预处理区"},
            "曝气沉砂池": {"x": 550, "y": 100, "width": 140, "height": 80, "area": "预处理区"},
            "膜格栅": {"x": 700, "y": 100, "width": 120, "height": 80, "area": "预处理区"},

            # 生物处理区（中间横向排列）
            "厌氧池": {"x": 100, "y": 200, "width": 120, "height": 80, "area": "生物处理区"},
            "缺氧池": {"x": 250, "y": 200, "width": 120, "height": 80, "area": "生物处理区"},
            "好氧池": {"x": 400, "y": 200, "width": 120, "height": 80, "area": "生物处理区"},
            "MBR膜池": {"x": 550, "y": 200, "width": 120, "height": 80, "area": "生物处理区"},
            "DF系统": {"x": 700, "y": 200, "width": 120, "height": 80, "area": "生物处理区"},

            # 深度处理区（右侧纵向排列）
            "催化氧化": {"x": 850, "y": 100, "width": 130, "height": 80, "area": "深度处理区"},
            "臭氧": {"x": 850, "y": 200, "width": 130, "height": 80, "area": "深度处理区"},
            "次氯酸钠": {"x": 1000, "y": 150, "width": 130, "height": 80, "area": "深度处理区"},

            # 污泥处理区（底部）
            "污泥处理车间": {"x": 400, "y": 300, "width": 180, "height": 80, "area": "污泥处理区"},
            "离心浓缩机": {"x": 300, "y": 350, "width": 130, "height": 80, "area": "污泥处理区"},
            "离心脱水机": {"x": 500, "y": 350, "width": 130, "height": 80, "area": "污泥处理区"},

            # 辅助设施
            "鼓风机房": {"x": 400, "y": 250, "width": 120, "height": 80, "area": "辅助设施"},
            "生物除臭": {"x": 700, "y": 50, "width": 130, "height": 80, "area": "辅助设施"}
        }

    def _initialize_connections(self):
        """定义管道连接关系，与PDF图纸一致"""
        return [
            # 主流程（蓝色）
            ("粗格栅", "提升泵房", '#1e88e5', "main"),
            ("提升泵房", "细格栅", '#1e88e5', "main"),
            ("细格栅", "曝气沉砂池", '#1e88e5', "main"),
            ("曝气沉砂池", "膜格栅", '#1e88e5', "main"),
            ("膜格栅", "催化氧化", '#1e88e5', "main"),
            ("膜格栅", "厌氧池", '#1e88e5', "main"),
            ("催化氧化", "臭氧", '#1e88e5', "main"),
            ("臭氧", "次氯酸钠", '#1e88e5', "main"),

            # 生物处理流程（绿色）
            ("厌氧池", "缺氧池", '#4CAF50', "bio"),
            ("缺氧池", "好氧池", '#4CAF50', "bio"),
            ("好氧池", "MBR膜池", '#4CAF50', "bio"),
            ("MBR膜池", "DF系统", '#4CAF50', "bio"),
            ("DF系统", "臭氧", '#4CAF50', "bio"),

            # 污泥流程（棕色）
            ("MBR膜池", "污泥处理车间", '#795548', "sludge"),
            ("污泥处理车间", "离心浓缩机", '#795548', "sludge"),
            ("离心浓缩机", "离心脱水机", '#795548', "sludge"),

            # 辅助流程
            ("鼓风机房", "好氧池", '#9e9e9e', "air"),

            # 臭气流程（紫色）
            ("粗格栅", "生物除臭", '#9c27b0', "gas"),
            ("提升泵房", "生物除臭", '#9c27b0', "gas"),
            ("细格栅", "生物除臭", '#9c27b0', "gas"),
            ("曝气沉砂池", "生物除臭", '#9c27b0', "gas"),
            ("膜格栅", "生物除臭", '#9c27b0', "gas"),
            ("污泥处理车间", "生物除臭", '#9c27b0', "gas")
        ]

    def _is_path_active(self, start_unit, end_unit):
        """检查路径是否激活（上下游单元都启用）"""
        start_active = self.unit_data.get(start_unit, {}).get("enabled", False)
        end_active = self.unit_data.get(end_unit, {}).get("enabled", False)
        return start_active and end_active

    def _create_flow_particles(self, flow_position):
        """创建水流粒子，基于当前流动位置"""
        particles = []
        for start_unit, end_unit, color, flow_type in self.connections:
            if not self._is_path_active(start_unit, end_unit):
                continue

            if start_unit in self.unit_coords and end_unit in self.unit_coords:
                start_coords = self.unit_coords[start_unit]
                end_coords = self.unit_coords[end_unit]

                # 计算起点和终点坐标
                start_x = start_coords["x"] + start_coords["width"]
                start_y = start_coords["y"] + start_coords["height"] / 2
                end_x = end_coords["x"]
                end_y = end_coords["y"] + end_coords["height"] / 2

                # 计算水流粒子位置 - 创建多个粒子以形成流动效果
                num_particles = 5
                for i in range(num_particles):
                    # 粒子间距和位置计算
                    phase = (flow_position + i * 20) % 100
                    progress = phase / 100.0

                    # 曲线流动效果
                    curve_factor = 0.1 * np.sin(progress * np.pi)
                    flow_x = start_x + (end_x - start_x) * progress + curve_factor * (end_y - start_y)
                    flow_y = start_y + (end_y - start_y) * progress - curve_factor * (end_x - start_x)

                    # 根据流程类型调整粒子大小和透明度
                    size = 8 if flow_type == "main" else 6
                    opacity = 0.8 if flow_type == "main" else 0.6
                    particles.append((flow_x, flow_y, color, size, opacity))

        return particles

    def render(self, animation_active=True, flow_position=0):
        """渲染交互式工艺图，完全复刻PDF图纸"""
        fig = go.Figure()

        # 绘制背景区域
        areas = {
            "预处理区": {"x": 80, "y": 80, "width": 750, "height": 120, "color": "rgba(220, 240, 255, 0.5)"},
            "生物处理区": {"x": 80, "y": 180, "width": 750, "height": 120, "color": "rgba(220, 255, 220, 0.5)"},
            "深度处理区": {"x": 830, "y": 80, "width": 350, "height": 220, "color": "rgba(255, 240, 220, 0.5)"},
            "污泥处理区": {"x": 280, "y": 280, "width": 400, "height": 180, "color": "rgba(255, 220, 220, 0.5)"},
            "辅助设施": {"x": 680, "y": 30, "width": 200, "height": 120, "color": "rgba(240, 220, 255, 0.5)"}
        }

        for area, props in areas.items():
            fig.add_shape(
                type="rect",
                x0=props["x"],
                y0=props["y"],
                x1=props["x"] + props["width"],
                y1=props["y"] + props["height"],
                line=dict(color="rgba(0,0,0,0.2)", width=1),
                fillcolor=props["color"],
                layer="below"
            )
            fig.add_annotation(
                x=props["x"] + props["width"] / 2,
                y=props["y"] + props["height"] + 15,
                text=area,
                showarrow=False,
                font=dict(size=14, color="black", weight="bold")
            )

        # 绘制工艺单元（矢量矩形）
        scatter_x, scatter_y, scatter_text, scatter_customdata = [], [], [], []
        for unit, coords in self.unit_coords.items():
            unit_info = self.unit_data.get(unit, {})
            emission = unit_info.get("emission", 0)
            enabled = unit_info.get("enabled", True)

            # 根据状态和排放量确定颜色
            if not enabled:
                color = 'rgba(200, 200, 200, 0.7)'  # 灰色表示关闭
            elif emission > 2000:
                color = 'rgba(255, 100, 100, 0.7)'  # 红色表示高排放
            elif emission > 1000:
                color = 'rgba(255, 200, 100, 0.7)'  # 橙色表示中高排放
            else:
                color = 'rgba(100, 200, 100, 0.7)'  # 绿色表示低排放

            # 绘制矩形作为工艺单元
            fig.add_shape(
                type="rect",
                x0=coords["x"],
                y0=coords["y"],
                x1=coords["x"] + coords["width"],
                y1=coords["y"] + coords["height"],
                line=dict(color="black", width=2),
                fillcolor=color,
                opacity=0.9,
                layer="below"
            )

            # 添加单元名称标签
            fig.add_annotation(
                x=coords["x"] + coords["width"] / 2,
                y=coords["y"] + coords["height"] / 2 + 5,
                text=unit,
                showarrow=False,
                font=dict(size=12, color="black", family="Arial", weight="bold")
            )

            # 添加排放量标签
            fig.add_annotation(
                x=coords["x"] + coords["width"] / 2,
                y=coords["y"] + coords["height"] / 2 - 15,
                text=f"{emission:.1f} kgCO2eq",
                showarrow=False,
                font=dict(size=10, color="black")
            )

            # 添加运行状态标签
            status_text = "运行中" if enabled else "已关闭"
            status_color = "green" if enabled else "red"
            fig.add_annotation(
                x=coords["x"] + coords["width"] / 2,
                y=coords["y"] - 10,
                text=status_text,
                showarrow=False,
                font=dict(size=10, color=status_color, weight="bold")
            )

            # 添加透明点击区域（实现交互）
            center_x = coords["x"] + coords["width"] / 2
            center_y = coords["y"] + coords["height"] / 2
            scatter_x.append(center_x)
            scatter_y.append(center_y)
            scatter_text.append(
                f"单元: {unit}<br>排放: {emission:.1f} kgCO2eq<br>状态: {'运行中' if enabled else '关闭'}"
            )
            scatter_customdata.append(unit)

        # 添加透明点击层
        fig.add_trace(go.Scatter(
            x=scatter_x,
            y=scatter_y,
            mode='markers',
            marker=dict(size=40, color='rgba(0,0,0,0)', opacity=0),
            text=scatter_text,
            hoverinfo="text",
            customdata=scatter_customdata,
            name="点击交互层"
        ))

        # 绘制管道连接
        for start_unit, end_unit, color, flow_type in self.connections:
            if start_unit in self.unit_coords and end_unit in self.unit_coords:
                start_coords = self.unit_coords[start_unit]
                end_coords = self.unit_coords[end_unit]

                # 计算起点和终点坐标
                start_x = start_coords["x"] + start_coords["width"]
                start_y = start_coords["y"] + start_coords["height"] / 2
                end_x = end_coords["x"]
                end_y = end_coords["y"] + end_coords["height"] / 2

                # 计算控制点（用于曲线）
                mid_x = (start_x + end_x) / 2
                mid_y = (start_y + end_y) / 2

                # 根据连接类型调整曲线
                if flow_type == "main":
                    # 主流程使用较粗的线
                    line_width = 4
                else:
                    line_width = 3

                # 根据状态调整颜色透明度
                if self._is_path_active(start_unit, end_unit):
                    line_opacity = 1.0
                else:
                    line_opacity = 0.3

                # 绘制带箭头的曲线管道
                fig.add_trace(go.Scatter(
                    x=[start_x, mid_x, end_x],
                    y=[start_y, mid_y, end_y],
                    mode='lines',
                    line=dict(
                        color=color,
                        width=line_width,
                        shape='spline'
                    ),
                    opacity=line_opacity,
                    hoverinfo='none',
                    showlegend=False
                ))

                # 添加箭头
                if self._is_path_active(start_unit, end_unit):
                    fig.add_annotation(
                        x=end_x,
                        y=end_y,
                        ax=mid_x,
                        ay=mid_y,
                        xref='x',
                        yref='y',
                        axref='x',
                        ayref='y',
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1.5,
                        arrowwidth=2,
                        arrowcolor=color
                    )

        # 添加动态水流效果
        if animation_active:
            flow_particles = self._create_flow_particles(flow_position)
            if flow_particles:
                flow_x, flow_y, flow_colors, flow_sizes, flow_opacities = zip(*flow_particles)
                fig.add_trace(go.Scatter(
                    x=flow_x,
                    y=flow_y,
                    mode='markers',
                    marker=dict(
                        size=flow_sizes,
                        color=flow_colors,
                        opacity=flow_opacities,
                        symbol='circle'
                    ),
                    showlegend=False,
                    hoverinfo='none'
                ))

        # 添加图例
        fig.add_trace(go.Scatter(
            x=[1150], y=[650],
            mode='markers',
            marker=dict(size=10, color='#1e88e5'),
            text='主流程',
            hoverinfo='text',
            showlegend=False
        ))
        fig.add_trace(go.Scatter(
            x=[1150], y=[620],
            mode='markers',
            marker=dict(size=10, color='#4CAF50'),
            text='生物处理流程',
            hoverinfo='text',
            showlegend=False
        ))
        fig.add_trace(go.Scatter(
            x=[1150], y=[590],
            mode='markers',
            marker=dict(size=10, color='#795548'),
            text='污泥流程',
            hoverinfo='text',
            showlegend=False
        ))
        fig.add_trace(go.Scatter(
            x=[1150], y=[560],
            mode='markers',
            marker=dict(size=10, color='#9c27b0'),
            text='臭气流程',
            hoverinfo='text',
            showlegend=False
        ))

        # 设置布局
        fig.update_layout(
            title='污水处理工艺流程仿真（基于PDF图纸）',
            title_font=dict(size=24, family="Arial", color="black"),
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                visible=False,
                range=[0, 1200]
            ),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                visible=False,
                range=[400, 0]  # 反转Y轴，使顶部为0
            ),
            plot_bgcolor='rgba(245,245,245,1)',
            paper_bgcolor='rgba(245,245,245,1)',
            height=700,
            width=1200,
            hovermode='closest',
            showlegend=False,
            clickmode='event+select'  # 启用点击事件
        )

        return fig
