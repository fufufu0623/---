from flask import Flask, render_template, request
import pandas as pd
import pulp

app = Flask(__name__)

# カスタムフィルタの定義
def format_float(value, precision=2):
    return format(value, f'.{precision}f')

# フィルタをアプリに登録
app.jinja_env.filters['format_float'] = format_float

@app.route('/')
def index():
    return render_template('index.html')

def solve_optimization_problem_with_penalty(data, constraints, objective, min_items=None, max_items=None, maximize=False, max_solutions=5):
    solutions = []
    nutritional_totals = []
    item_penalties = {i: 0 for i in data.index}
    problem = pulp.LpProblem("Menu_Optimization", pulp.LpMaximize if maximize else pulp.LpMinimize)
    menu_vars = pulp.LpVariable.dicts("Menu", data.index, cat=pulp.LpBinary)

    while len(solutions) < max_solutions:
        if objective in data.columns:
            problem += pulp.lpSum([(data.loc[i, objective] + item_penalties[i]) * menu_vars[i] for i in data.index])

        for nutrient, (constraint_type, value) in constraints.items():
            if nutrient in data.columns:
                if constraint_type == 'min':
                    problem += pulp.lpSum([data.loc[i, nutrient] * menu_vars[i] for i in data.index]) >= value
                elif constraint_type == 'max':
                    problem += pulp.lpSum([data.loc[i, nutrient] * menu_vars[i] for i in data.index]) <= value
                elif constraint_type == 'ave':
                    problem += pulp.lpSum([data.loc[i, nutrient] * menu_vars[i] for i in data.index]) >= value * pulp.lpSum([menu_vars[i] for i in data.index])

        if min_items is not None:
            problem += pulp.lpSum(menu_vars[i] for i in data.index) >= min_items
        if max_items is not None:
            problem += pulp.lpSum(menu_vars[i] for i in data.index) <= max_items

        problem.solve()
        if pulp.LpStatus[problem.status] == 'Optimal':
            selected_items = [i for i in data.index if menu_vars[i].varValue == 1]
            solutions.append(selected_items)
            # 栄養価の計算
            nutritional_totals.append({
                'Calories': sum(data.loc[i, 'カロリー'] * menu_vars[i].varValue for i in selected_items),
                'Protein': sum(data.loc[i, 'タンパク質'] * menu_vars[i].varValue for i in selected_items),
                'Carbs': sum(data.loc[i, '炭水化物'] * menu_vars[i].varValue for i in selected_items),
                'Fat': sum(data.loc[i, '脂質'] * menu_vars[i].varValue for i in selected_items),
                'Salt': sum(data.loc[i, '塩分'] * menu_vars[i].varValue for i in selected_items),
                'Human Rights': sum(data.loc[i, '人権'] * menu_vars[i].varValue for i in selected_items) / len(selected_items) if selected_items else 0
            })
            for i in selected_items:
                item_penalties[i] += data.loc[i, 'カロリー'] 
            problem = pulp.LpProblem("Menu_Optimization", pulp.LpMaximize if maximize else pulp.LpMinimize)
        else:
            break

    return solutions, nutritional_totals

@app.route('/solve', methods=['POST'])
def solve():
    protein_min = float(request.form['protein_min'])
    salt_max = float(request.form['salt_max'])
    carbs_max = float(request.form['carbs_max'])
    fat_max = float(request.form['fat_max'])
    calories_max = float(request.form['calories_max'])
    human_rights_ave = float(request.form['human_rights_ave'])
    min_items = int(request.form.get('min_items', 3))  # デフォルト値を3に設定
    max_items = int(request.form.get('max_items', 5))  # デフォルト値を5に設定

    data = pd.read_csv('鳥貴族.csv')

    constraints = {
        'タンパク質': ('min', protein_min),
        '塩分': ('max', salt_max),
        '炭水化物': ('max', carbs_max),
        '脂質': ('max', fat_max),
        'カロリー': ('max', calories_max),
        '人権': ('ave', human_rights_ave)
    }

    solutions, nutritional_totals = solve_optimization_problem_with_penalty(data, constraints, 'カロリー', min_items=min_items, max_items=5, max_solutions=10)

    # 解のデータを展開
    detailed_solutions = []
    for solution in solutions:
        detailed_solutions.append([(data.loc[item, 'メニュー名'], data.loc[item, 'カロリー']) for item in solution])

    zipped_solutions = zip(detailed_solutions, nutritional_totals)

    return render_template('results.html', zipped_solutions=zipped_solutions)

if __name__ == '__main__':
    app.run(debug=True)
