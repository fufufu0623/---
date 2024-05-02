from flask import Flask, render_template, request
import pandas as pd
import pulp

app = Flask(__name__)

def format_float(value, precision=2):
    try:
        float_value = float(value)
    except (TypeError, ValueError) as e:
        print(f"Error converting value: {value} to float. Error: {e}")  # ログ出力
        return format(0, f'.{precision}f')
    else:
        return format(float_value, f'.{precision}f')


# フィルタをアプリに登録
app.jinja_env.filters['format_float'] = format_float

@app.route('/')
def index():
    return render_template('index.html')

def solve_optimization_problem_with_penalty(data, constraints, objective, human_rights_ave, min_items=None, max_items=None, maximize=False, max_solutions=5):
    solutions = []
    nutritional_totals = []
    item_penalties = {i: 0 for i in data.index}
    for _ in range(max_solutions):
        problem = pulp.LpProblem("Menu_Optimization", pulp.LpMaximize if maximize else pulp.LpMinimize)
        menu_vars = pulp.LpVariable.dicts("Menu", data.index, cat=pulp.LpBinary)
        
        # 目的関数の追加
        problem += pulp.lpSum([(data.loc[i, objective] + item_penalties[i]) * menu_vars[i] for i in data.index])

        # 制約の追加
        for nutrient, bounds in constraints.items():
            if nutrient == '人権':
                problem += pulp.lpSum([data.loc[i, nutrient] * menu_vars[i] for i in data.index]) >= human_rights_ave * pulp.lpSum([menu_vars[i] for i in data.index])

            else:
                min_val, max_val = bounds
                problem += pulp.lpSum([data.loc[i, nutrient] * menu_vars[i] for i in data.index]) >= min_val
                problem += pulp.lpSum([data.loc[i, nutrient] * menu_vars[i] for i in data.index]) <= max_val

        if min_items is not None:
            problem += pulp.lpSum(menu_vars.values()) >= min_items
        if max_items is not None:
            problem += pulp.lpSum(menu_vars.values()) <= max_items

        problem.solve()
        if pulp.LpStatus[problem.status] == 'Optimal':
            selected_items = [i for i, var in menu_vars.items() if var.varValue == 1]
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
    # フォームデータを受け取る
    protein_min = float(request.form.get('protein_min', 0))
    protein_max = float(request.form.get('protein_max', 100))  # デフォルト値を設定
    salt_min = float(request.form.get('salt_min', 0))         # 塩分の最小値
    salt_max = float(request.form.get('salt_max', 10))
    carbs_min = float(request.form.get('carbs_min', 0))       # 炭水化物の最小値
    carbs_max = float(request.form.get('carbs_max', 50))
    fat_min = float(request.form.get('fat_min', 0))           # 脂質の最小値
    fat_max = float(request.form.get('fat_max', 10))
    calories_min = float(request.form.get('calories_min', 0)) # カロリーの最小値
    calories_max = float(request.form.get('calories_max', 1000))
    human_rights_ave = float(request.form.get('human_rights_ave', 0))
    min_items = int(request.form.get('min_items', 3))
    max_items = int(request.form.get('max_items', 5))

    # データファイルを読み込む
    data = pd.read_csv('鳥貴族.csv')

    # 制約を設定
    constraints = {
        'タンパク質': (protein_min, protein_max),
        '塩分': (salt_min, salt_max),
        '炭水化物': (carbs_min, carbs_max),
        '脂質': (fat_min, fat_max),
        'カロリー': (calories_min, calories_max),
        '人権': (human_rights_ave) 
    }

    # 最適化問題を解く
    solutions, nutritional_totals = solve_optimization_problem_with_penalty(data, constraints, 'カロリー', human_rights_ave, min_items=min_items, max_items=max_items, max_solutions=10)
    # 解のデータを表示用に整形
    detailed_solutions = []
    for solution in solutions:
        detailed_solutions.append([(data.loc[item, 'メニュー名'], data.loc[item, 'カロリー']) for item in solution])
    # 結果をテンプレートに渡す
    zipped_solutions = zip(detailed_solutions, nutritional_totals)
    return render_template('results.html', zipped_solutions=zipped_solutions)



if __name__ == '__main__':
    app.run(debug=True)
